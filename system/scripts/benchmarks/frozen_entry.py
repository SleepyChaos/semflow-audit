"""Start a module against one immutable implementation, without importing the app."""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation", type=Path, required=True)
    entry = parser.add_mutually_exclusive_group(required=True)
    entry.add_argument("--module")
    entry.add_argument("--script", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = args.implementation.resolve() / "implementation/system"
    if not (root / "backend/app/__init__.py").exists():
        raise RuntimeError("Frozen application is missing")
    env = {**os.environ, "PYTHONPATH": f"{root / 'backend'}:{root}"}
    values = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    command = ["-m", args.module] if args.module else [str(args.script.resolve())]
    os.execvpe(sys.executable, [sys.executable, *command, *values], env)


if __name__ == "__main__":
    main()
