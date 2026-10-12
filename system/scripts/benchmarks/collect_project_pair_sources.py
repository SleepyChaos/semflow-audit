"""Collect preselected source pairs only; no upstream code or tests are executed."""

import argparse
import hashlib
import json
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import HTTPException
from pathlib import Path

from prepare_real_pairs import collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    selection = json.loads(args.selection.read_text())
    records = []
    for source in selection["selected"]:
        key = f"{source['repository']}:{source['prePatch']['commit']}"
        records.append(
            {
                "case_id": "pair-" + hashlib.sha256(key.encode()).hexdigest()[:16],
                "cve": source["CVE"],
                "repository": source["repository"],
                "pre_commit": source["prePatch"]["commit"],
                "post_commit": source["postPatch"]["commit"],
                "labels": source["prePatch"]["weaknesses"],
                "cwes": source.get("CWEs", []),
                "language": "javascript",
                "split": "formal_holdout_candidate_not_adjudicated",
                "oracle_status": "not_validated",
                "label_status": "upstream_unadjudicated",
                "collection_status": "pending",
                "test_execution": "not_run",
                "input_sanitization": "not_prepared",
            }
        )
    receipt = {
        "scope": "Full pre/post source snapshots, collection only",
        "selection_policy": selection["policy"],
        "selection_sha256": hashlib.sha256(args.selection.read_bytes()).hexdigest(),
        "records": records,
    }
    manifest = args.output / "manifest.json"
    # The manifest contains evaluator labels; never upload this directory directly.
    manifest.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(collect, args.output, row): row for row in records}
        for future in as_completed(futures):
            row = futures[future]
            try:
                future.result()
                for variant in ("pre", "post"):
                    location = row["labels"][0]["location"]
                    target = args.output / row["case_id"] / variant / location["file"]
                    row["snapshots"][variant]["target_file_present"] = target.is_file()
            except (OSError, ValueError, KeyError, tarfile.TarError, HTTPException) as exc:
                row.update(
                    collection_status="failed",
                    error_type=type(exc).__name__,
                    error=str(exc)[:300],
                )
            manifest.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
            print(
                json.dumps(
                    {"case_id": row["case_id"], "status": row["collection_status"]}
                ),
                flush=True,
            )
    print("MANIFEST=" + str(manifest), flush=True)


if __name__ == "__main__":
    main()
