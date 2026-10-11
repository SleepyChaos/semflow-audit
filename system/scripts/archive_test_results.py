"""Archive existing test versions and results without executing any test jobs."""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system"))

from scripts.test_archive.store import freeze, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("archive_id", help="Example: 20261009-workspace-v1")
    parser.add_argument(
        "--offline-environment",
        action="store_true",
        help="Do not contact Docker; record service image identities as unobserved",
    )
    parser.add_argument(
        "--archive-only",
        action="store_true",
        help="Verify copies, permit originals to evolve",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,79}", args.archive_id):
        parser.error(
            "archive_id must contain only lowercase letters, digits and hyphens"
        )
    if args.action == "create":
        result = freeze(
            ROOT, args.archive_id, offline_environment=args.offline_environment
        )
    else:
        problems = verify(ROOT, args.archive_id, originals=not args.archive_only)
        result = {
            "archive_id": args.archive_id,
            "verification": "failed" if problems else "passed",
            "scope": "archive_only"
            if args.archive_only
            else "archive_and_original_results",
            "problems": problems,
        }
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 1 if result.get("verification") == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
