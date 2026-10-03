"""Execute only our constructed fixtures with Flask's test client; no browser/server."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from scripts.benchmarks.flask_cases import cases, dataset_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = cases()
    payload = '<img src=x onerror="alert(1)">'
    report = {"scope": "runtime reflection/MIME calibration of 12 original fixtures; no GUI, no upstream code execution",
              "dataset_hash": dataset_hash(rows), "records": []}
    from importlib.metadata import version
    report["flask_version"] = version("flask")
    for row in rows:
        namespace = {"__name__": "original_flask_oracle"}
        exec(compile(row["source"], row["file"], "exec"), namespace)  # noqa: S102 - only original fixed fixtures from cases(), never CLI or downloaded source
        app = namespace["app"]
        client = app.test_client()
        if row["id"] == "routed_parameter":
            response = client.get("/" + quote(payload, safe=""))
        elif row["id"] in {"app_post", "bp_post", "constant"}:
            response = client.post("/view", query_string={"payload": payload})
        else:
            response = client.get("/view", query_string={"payload": payload})
        body = response.get_data(as_text=True)
        reflected = response.status_code == 200 and response.mimetype == "text/html" and payload in body
        record = {"id": row["id"], "expected": row["vulnerable"],
                  "observed_unescaped_html": reflected, "status_code": response.status_code,
                  "mimetype": response.mimetype, "source_sha256": hashlib.sha256(row["source"].encode()).hexdigest(),
                  "status": "passed" if reflected == row["vulnerable"] else "failed"}
        report["records"].append(record)
    report["status"] = "passed" if all(r["status"] == "passed" for r in report["records"]) else "failed"
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
