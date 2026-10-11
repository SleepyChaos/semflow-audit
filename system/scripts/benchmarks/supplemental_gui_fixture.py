"""Create/remove only this campaign's synthetic GUI account and terminal states."""

import argparse
import json
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from app.adapters.artifacts import ArtifactStore
from app.core.db import engine
from app.core.security import get_password_hash
from app.models import User
from app.persistence.audit_models import AuditRun
from sqlmodel import Session, select

from scripts.benchmarks.supplemental_prepare import ROOT, save, sha


def setup(output, url="http://127.0.0.1:5173"):
    private = output / "credentials.private.json"
    if private.exists():
        raise RuntimeError("Refuse to replace an existing GUI fixture")
    owner = uuid4()
    password = "Gui-probe-" + uuid4().hex
    runs = []
    email = f"gui-{owner}@example.com"
    with Session(engine) as db:
        db.add(
            User(
                id=owner,
                email=email,
                hashed_password=get_password_hash(password),
                is_active=True,
            )
        )
        db.commit()
        for state in ("failed", "completed"):
            run_id = uuid4()
            directory = ArtifactStore().directory(str(run_id))
            (directory / "source").mkdir()
            (directory / "source/main.py").write_text(
                "print('GUI synthetic state fixture')\n"
            )
            (directory / "execution.log").write_text(
                "Synthetic terminal-state GUI fixture; no scan/model request.\n"
            )
            db.add(
                AuditRun(
                    id=run_id,
                    owner_id=owner,
                    source_run_id=run_id,
                    project_name=f"supplemental-gui-{state}",
                    language="python",
                    status=state,
                    phase=state,
                    snapshot_hash="0" * 64,
                    query_pack="codeql/python-queries@1.6.0",
                    suite="codeql-suites/python-code-scanning.qls",
                    error="Synthetic scanner failure: no successful empty result"
                    if state == "failed"
                    else None,
                    coverage={"synthetic_state_fixture": True},
                )
            )
            runs.append(str(run_id))
        db.commit()
    save(
        private,
        {"owner": str(owner), "email": email, "password": password, "run_ids": runs},
    )
    private.chmod(0o600)
    save(
        output / "config.json",
        {
            "scope": "Real browser/API/DB with synthetic terminal states; no Worker, model generation, rule publication, or completed upload-to-four-stage claim",
            "browser_path": "Browser plugin not available; regular Playwright",
            "url": url,
            "api_url": "http://127.0.0.1:8000",
            "viewports": [
                {"width": 1440, "height": 1000},
                {"width": 390, "height": 844},
            ],
            "frontend_hashes": {
                p.relative_to(ROOT).as_posix(): sha(p)
                for p in (ROOT / "system/frontend/src").rglob("*")
                if p.is_file()
            },
            "fixture_generator_sha256": sha(Path(__file__)),
            "browser_script_sha256": sha(
                ROOT / "system/scripts/benchmarks/supplemental_gui.mjs"
            ),
        },
    )


def cleanup(output):
    private = output / "credentials.private.json"
    saved = json.loads(private.read_text())
    owner = UUID(saved["owner"])
    ids = {UUID(value) for value in saved["run_ids"]}
    with Session(engine) as db:
        rows = db.exec(select(AuditRun).where(AuditRun.owner_id == owner)).all()
        if not {row.id for row in rows}.issubset(ids):
            raise RuntimeError(
                "Unexpected owned tasks; preserve fixture for inspection"
            )
        user = db.get(User, owner)
        if (
            user.email != saved["email"]
            or not user.email.startswith("gui-")
            or not user.email.endswith(("@research.invalid", "@example.com"))
        ):
            raise RuntimeError("Refuse to delete a non-fixture account")
        for row in rows:
            db.delete(row)
        db.flush()
        db.delete(user)
        db.commit()
    for run_id in ids:
        shutil.rmtree(ArtifactStore().directory(str(run_id)), ignore_errors=True)
    private.unlink()
    save(
        output / "cleanup-receipt.json",
        {
            "synthetic_users_removed": 1,
            "synthetic_runs_removed": len(ids),
            "credentials_removed": True,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "cleanup"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    if args.action == "setup":
        setup(args.output.resolve(), args.base_url)
    else:
        cleanup(args.output.resolve())


if __name__ == "__main__":
    main()
