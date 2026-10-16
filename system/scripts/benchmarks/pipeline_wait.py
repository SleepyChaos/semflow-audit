"""Wait for an existing controller without launching or replaying its work."""

import argparse
import json
import time
from pathlib import Path

from scripts.benchmarks.mechanical_monitor import observe
from scripts.benchmarks.mechanical_pipeline import save


def check(output):
    state = observe(output)
    if state["status"] == "completed":
        return True, state
    if state["status"] != "running":
        raise RuntimeError(f"Upstream pipeline requires attention: {state}")
    return False, state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    previous = None
    while True:
        try:
            completed, state = check(args.upstream)
        except RuntimeError as error:
            save(args.receipt, {"status": "blocked", "error": str(error)})
            raise
        save(args.receipt, state)
        signature = (state["status"], state.get("log_bytes"))
        if signature != previous:
            print(json.dumps(state), flush=True)
            previous = signature
        if completed:
            return
        time.sleep(30)


if __name__ == "__main__":
    main()
