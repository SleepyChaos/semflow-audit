"""Retain safe project copies and export only authorized, effective source edits."""

import ast
import difflib
import hashlib
import shutil
import warnings
from pathlib import Path

from pydantic import ValidationError

from app.adapters.repair.patches import safe_file
from app.adapters.snapshot import snapshot_digest
from app.contracts.stages import RepairResponse
from app.domain.audit import AuditError

CACHES = {"__pycache__", ".pytest_cache", ".hypothesis", ".mypy_cache", ".ruff_cache"}


def retain_source(source, destination):
    """Normalize internal document aliases only; never follow arbitrary links."""
    source, destination = Path(source).resolve(), Path(destination)
    if destination.exists():
        raise AuditError("Retained source destination already exists")
    aliases = []
    for file in source.rglob("*"):
        if file.is_symlink():
            target = file.resolve()
            if (
                file.suffix.lower() != ".md"
                or not target.is_relative_to(source)
                or not target.is_file()
                or target.suffix.lower() != ".md"
                or target.stat().st_size > 100000
            ):
                raise AuditError(
                    "Unsupported source link; source was not copied",
                    code="source_unsupported",
                )
            aliases.append(
                {"file": str(file.relative_to(source)), "target": str(file.readlink())}
            )
    shutil.copytree(source, destination, symlinks=False)
    return {
        "retained_snapshot": snapshot_digest(destination),
        "normalized_document_aliases": aliases,
    }


def inventory(root):
    rows = {}
    for path in root.rglob("*"):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise AuditError("Agent created a symbolic link; candidate rejected")
        if path.is_file() and not set(path.relative_to(root).parts) & CACHES:
            rows[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def replacement_chunks(name, old, new):
    """Export exact unique hunks, avoiding two complete copies of a large file."""
    before, after = old.splitlines(True), new.splitlines(True)
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for context in (3, 8, 20):
        chunks = []
        for group in matcher.get_grouped_opcodes(context):
            old_text = "".join(before[group[0][1] : group[-1][2]])
            new_text = "".join(after[group[0][3] : group[-1][4]])
            if not old_text or old.count(old_text) != 1:
                break
            chunks.append(
                {
                    "file": name,
                    "old_text": old_text,
                    "new_text": new_text,
                    "reason": "OpenHands 隔离执行产生的候选；需平台独立验证后再接受",
                }
            )
        else:
            return chunks
    raise AuditError(
        "Cannot export unique bounded source replacements",
        code="candidate_export_failed",
    )


def coalesce_replacements(changes, originals, maximum=8):
    """Join the nearest same-file windows without changing the resulting bytes."""
    changes = list(changes)
    while len(changes) > maximum:
        choices = []
        for index, (left, right) in enumerate(zip(changes, changes[1:], strict=False)):
            if left["file"] != right["file"]:
                continue
            old = originals[left["file"]]
            start = old.index(left["old_text"])
            middle = start + len(left["old_text"])
            next_start = old.index(right["old_text"])
            end = next_start + len(right["old_text"])
            if middle > next_start:
                continue
            merged = {
                **left,
                "old_text": old[start:end],
                "new_text": left["new_text"]
                + old[middle:next_start]
                + right["new_text"],
            }
            if max(len(merged["old_text"]), len(merged["new_text"])) <= 50000:
                choices.append((next_start - middle, index, merged))
        if not choices:
            raise AuditError(
                "Cannot represent candidate within bounded platform replacements",
                code="candidate_export_failed",
            )
        _, index, merged = min(choices, key=lambda item: (item[0], item[1]))
        changes[index : index + 2] = [merged]
    return changes


def export_candidate(source, workspace, allowed_paths, summary):
    original, changed = inventory(source), inventory(workspace)
    names = sorted(
        name
        for name in original.keys() | changed.keys()
        if original.get(name) != changed.get(name)
    )
    if not names:
        raise AuditError("Agent produced no source changes", code="candidate_unchanged")
    forbidden = sorted(set(names) - set(allowed_paths))
    if forbidden:
        raise AuditError(
            "Agent modified unauthorized files: " + ", ".join(forbidden),
            code="scope_violation",
        )
    changes, patch, effective, originals = [], [], False, {}
    for name in names:
        old_path = safe_file(source, name)
        new_path = safe_file(workspace, name)
        if name not in original or name not in changed:
            raise AuditError(
                "This repair adapter requires retained existing target files"
            )
        if max(old_path.stat().st_size, new_path.stat().st_size) > 1024 * 1024:
            raise AuditError("Agent target exceeds platform replacement size limit")
        old, new = old_path.read_text(), new_path.read_text()
        originals[name] = old
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            try:
                effective |= name.endswith(".py") and ast.dump(
                    ast.parse(old)
                ) != ast.dump(ast.parse(new))
            except SyntaxError:
                effective = True  # Independent syntax validation decides eligibility.
        effective |= not name.endswith(".py") and old != new
        changes.extend(replacement_chunks(name, old, new))
        patch.extend(
            difflib.unified_diff(
                old.splitlines(True),
                new.splitlines(True),
                fromfile="a/" + name,
                tofile="b/" + name,
            )
        )
    if not effective:
        raise AuditError(
            "Only comments/formatting changed; no runtime repair",
            code="candidate_unchanged",
        )
    changes = coalesce_replacements(changes, originals)
    try:
        response = RepairResponse.model_validate(
            {"changes": changes, "summary": summary}
        )
    except ValidationError as error:
        raise AuditError(
            "Candidate exceeds platform representation limits",
            code="candidate_export_failed",
        ) from error
    return response, "".join(patch)


def writable_copy(source, destination, allowed_paths=None):
    if destination.exists():
        raise AuditError("Agent workspace already exists; do not replay paid work")
    shutil.copytree(source, destination, symlinks=True)
    for path in [destination, *destination.rglob("*")]:
        if path.is_symlink():
            raise AuditError("Agent workspace must use a retained link-free snapshot")
        if allowed_paths is None:
            path.chmod(0o777 if path.is_dir() else 0o666)
        elif path.is_dir():
            path.chmod(0o555)
        else:
            name = path.relative_to(destination).as_posix()
            path.chmod(0o666 if name in allowed_paths else 0o444)
