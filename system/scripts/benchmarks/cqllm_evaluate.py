"""Author database execution, deliberately separate from generation feedback."""

import json
import shutil
import stat
import subprocess
import time
import zipfile
from pathlib import Path, PurePosixPath

from app.adapters.codeql.custom import run_query
from app.adapters.codeql.scanner import CodeQLScanner
from scripts.benchmarks.cqllm_materials import RELEASE_SHA, RELEASE_URL, sha
from scripts.benchmarks.mechanical_pipeline import exclusive, save


def prepare_database(root):
    materials = root / "materials"
    materials.mkdir(exist_ok=True)
    archive = materials / "CQLLM.zip"
    with exclusive(materials / "download.lock"):
        if not archive.exists() or sha(archive) != RELEASE_SHA:
            with (materials / "download.log").open("a") as log:
                for attempt in range(3):
                    result = subprocess.run(
                        [
                            "curl",
                            "-L",
                            "--fail",
                            "--connect-timeout",
                            "30",
                            "--max-time",
                            "1800",
                            "-C",
                            "-",
                            "--output",
                            str(archive),
                            RELEASE_URL,
                        ],
                        stdout=log,
                        stderr=log,
                        check=False,
                    )
                    if result.returncode == 0 and sha(archive) == RELEASE_SHA:
                        break
                    if result.returncode == 0:
                        raise RuntimeError(
                            "Official release checksum mismatch; preserve downloaded material"
                        )
                    time.sleep(5 * (attempt + 1))
                else:
                    raise RuntimeError(
                        "Official database download failed after three resumable attempts"
                    )
        target = materials / "author-database"
        receipt = target / "prepared.json"
        if receipt.exists():
            return Path(json.loads(receipt.read_text())["database"])
        target.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            candidates = [
                x for x in bundle.namelist() if x.endswith("codeql-database.yml")
            ]
            if len(candidates) != 1:
                raise RuntimeError(
                    f"Expected one author database, found {len(candidates)}"
                )
            prefix = candidates[0].rsplit("/", 1)[0] + "/"
            for info in bundle.infolist():
                if not info.filename.startswith(prefix):
                    continue
                name = PurePosixPath(info.filename)
                if (
                    name.is_absolute()
                    or ".." in name.parts
                    or stat.S_ISLNK(info.external_attr >> 16)
                ):
                    raise RuntimeError("Unsafe path in official database archive")
                relative = PurePosixPath(info.filename[len(prefix) :])
                path = target.joinpath(*relative.parts)
                if info.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(info) as source, path.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
        save(
            receipt,
            {
                "database": str(target),
                "release_sha256": RELEASE_SHA,
                "cli": CodeQLScanner().version(),
                "reference_queries_excluded": True,
            },
        )
        return target


def evaluate(result, root, database):
    path = root / "arms" / result["arm"] / result["task_id"]
    final = path / "evaluation.json"
    if final.exists():
        return json.loads(final.read_text())
    row = {
        "task_id": result["task_id"],
        "arm": result["arm"],
        "status": "not_evaluated_not_compiled",
        "semantic_correct": None,
        "location_accuracy": None,
        "positive_negative_score": None,
    }
    if result["status"] == "compiled":
        try:
            findings = run_query(
                database,
                Path(result["pack"]),
                path / "author.sarif",
                path / "execution.log",
                RELEASE_SHA,
            )
            row.update(status="executed", alerts=len(findings), execution_success=True)
        except Exception as error:  # noqa: BLE001 - execution failure is not zero alerts
            row.update(status="execution_failed", error=str(error))
    save(final, row)
    return row
