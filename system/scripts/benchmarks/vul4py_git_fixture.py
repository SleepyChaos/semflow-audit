"""Restore evaluator-only Git history without changing tracked source bytes."""

import hashlib
import json
import os
import shutil
import subprocess

from scripts.benchmarks.mechanical_pipeline import save


def configure_safe_paths(case):
    for index, target in enumerate(("vulnerable", "fixed", "git-history")):
        os.environ[f"GIT_CONFIG_KEY_{index}"] = "safe.directory"
        os.environ[f"GIT_CONFIG_VALUE_{index}"] = str(case / target)
    os.environ["GIT_CONFIG_COUNT"] = "3"


def tracked_hashes(source):
    return {
        str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source.rglob("*")
        if p.is_file()
        and not p.is_symlink()
        and not any(
            part in {".git", ".venv", "__pycache__"}
            for part in p.relative_to(source).parts
        )
    }


def run(args, log):
    with log.open("a") as stream:
        stream.write("$ " + " ".join(args) + "\n")
        stream.flush()
        result = subprocess.run(
            args, stdout=stream, stderr=subprocess.STDOUT, timeout=600, check=False
        )
    if result.returncode:
        raise RuntimeError("Evaluator Git history restoration failed; see fixture log")


def restore(case, source, target, meta, logs, *, restore_submodules=False):
    final = logs / f"git-fixture-{target}.json"
    if final.exists():
        saved = json.loads(final.read_text())
        actual = tracked_hashes(source)
        if any(
            actual.get(name) != digest for name, digest in saved["file_hashes"].items()
        ):
            raise RuntimeError("Restored Git fixture source changed after receipt")
        return
    before = tracked_hashes(source)
    log = logs / "git-fixture.log"
    history = case / "git-history"
    if not history.exists():
        run(["git", "clone", "--no-checkout", meta["repo_url"], str(history)], log)
    reference = meta["versions"][target]["git_ref"]
    run(["git", "-C", str(history), "cat-file", "-e", reference + "^{commit}"], log)
    scratch = case / ("git-metadata-" + target)
    if (source / ".git").exists() or scratch.exists():
        raise RuntimeError("Partial Git fixture requires explicit recovery")
    run(["git", "clone", "--no-checkout", "--shared", str(history), str(scratch)], log)
    shutil.move(str(scratch / ".git"), str(source / ".git"))
    scratch.rmdir()
    # --mixed updates only history/index, never the tracked source under evaluation.
    run(["git", "-C", str(source), "reset", "--mixed", reference], log)
    submodule_paths = []
    if restore_submodules:
        listing = subprocess.check_output(
            ["git", "-C", str(source), "ls-files", "--stage"], text=True
        )
        submodule_paths = [
            line.split("\t", 1)[1]
            for line in listing.splitlines()
            if line.startswith("160000 ")
        ]
        run(
            [
                "git",
                "-C",
                str(source),
                "-c",
                "protocol.file.allow=always",
                "-c",
                "url.https://github.com/.insteadOf=git://github.com/",
                "submodule",
                "update",
                "--init",
                "--recursive",
            ],
            log,
        )
    after = tracked_hashes(source)
    added = set(after) - set(before)
    if any(after.get(name) != digest for name, digest in before.items()) or any(
        not any(name.startswith(prefix + "/") for prefix in submodule_paths)
        for name in added
    ):
        raise RuntimeError("Git fixture changed evaluated source bytes")
    save(
        final,
        {
            "repo_url": meta["repo_url"],
            "reference": reference,
            "history": "full, evaluator-only",
            "tracked_bytes_unchanged": True,
            "file_hashes": before,
            "restored_submodule_paths": submodule_paths,
            "evaluator_only_added_files": len(added),
            "model_inputs_changed": False,
        },
    )
