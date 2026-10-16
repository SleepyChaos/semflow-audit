"""Observe the owned controller and child; never start or retry test work."""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from scripts.benchmarks.mechanical_pipeline import save


def alive(pid):
    if not isinstance(pid, int) or pid < 1:
        return None
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return None


def observe(output):
    path = output / "status.json"
    if not path.exists():
        return {"status": "not_started"}
    state = json.loads(path.read_text())
    status = state["status"]
    result = {
        "status": status,
        "step": state.get("step"),
        "log_bytes": state.get("log_bytes"),
        "log": state.get("log"),
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    if status == "running":
        result["controller_alive"] = alive(state.get("controller_pid"))
        result["child_alive"] = alive(state.get("pid"))
        result["heartbeat_age_seconds"] = round(time.time() - path.stat().st_mtime, 1)
        if result["controller_alive"] is False:
            result["status"] = "controller_exited"
        elif result["heartbeat_age_seconds"] > 30:
            result["status"] = "heartbeat_stale"
        # A live PID or fresh heartbeat does not prove model/tool progress.
        result["progress_evidence"] = (
            "phase logs and task receipts; heartbeat is liveness only"
        )
    return result


def observe_work(root, artifacts):
    markers = list((root / "e2e/system").glob("*/scout.started.json"))
    if not markers:
        return {"status": "no_scout_receipt"}
    marker = max(markers, key=lambda p: p.stat().st_mtime)
    stage_id = str(UUID(json.loads(marker.read_text())["stage_id"]))
    path = artifacts / "runs" / stage_id / "scout-progress.json"
    if not path.exists():
        return {"status": "progress_not_instrumented", "stage_id": stage_id}
    work = json.loads(path.read_text())
    age = round(time.time() - path.stat().st_mtime, 1)
    return {
        **work,
        "stage_id": stage_id,
        "project": marker.parent.name,
        "receipt_age_seconds": age,
        "attention": "no_window_receipt_180s_check_inflight_call_or_tool"
        if work["status"] == "running" and age > 180
        else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--test-root", type=Path)
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    previous = None
    while True:
        result = observe(args.output)
        if args.test_root:
            result["work"] = observe_work(args.test_root, args.artifact_root)
        save(args.output / "monitor.json", result)
        signature = (
            result["status"],
            result.get("step"),
            result.get("log_bytes"),
            json.dumps(result.get("work", {}), sort_keys=True),
        )
        if signature != previous:
            print(json.dumps(result, ensure_ascii=False), flush=True)
            previous = signature
        if not args.watch or result["status"] != "running":
            return
        time.sleep(10)


if __name__ == "__main__":
    main()
