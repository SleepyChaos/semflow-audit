"""Finite writable source selection and actual target bodies before model use."""

import hashlib

from app.adapters.repair.patches import safe_file
from app.domain.audit import AuditError

SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")


def select_paths(inputs, targets, materials):
    paths = (
        inputs.allowed_paths
        or sorted({t.location["file"] for t in targets if t.location.get("file")})
        or sorted(
            {
                m["reference"]["file"]
                for m in materials
                if m["kind"] == "code"
                and m["reference"]["file"].endswith(SOURCE_SUFFIXES)
            }
        )
    )
    if not paths or len(paths) > 30:
        raise AuditError("需要明确有限的可修改文件")
    if not any(name.endswith(SOURCE_SUFFIXES) for name in paths):
        raise AuditError(
            "当前语义修复需要 Python/JavaScript/TypeScript 修改目标；模板或配置单独修复尚不支持",
            code="unsupported_repair_target",
        )
    return paths


def ensure_target_bodies(evidence, targets, materials, paths):
    result = list(materials)
    read_paths = {
        row["reference"].get("file") for row in materials if row["kind"] == "code"
    }
    for name in paths:
        if name.endswith(SOURCE_SUFFIXES) and name not in read_paths:
            line = next(
                (
                    max(1, t.location.get("line", 1))
                    for t in targets
                    if t.location.get("file") == name
                ),
                1,
            )
            result.append(evidence.read(name, max(1, line - 15), line + 35))
    return result


def patch_context(evidence, paths, materials):
    """Supply exactly the union of already-read writable source windows.

    File limits protect the local reader, not a model token quota. The original
    source remains immutable and the patch adapter applies exact replacements.
    """
    contents, views = {}, {}
    for name in paths:
        path = safe_file(evidence.root, name)
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise AuditError("修复文件无效或超过本地读取范围")
        text = path.read_text()
        lines = text.splitlines(keepends=True)
        refs = [
            r["reference"]
            for r in materials
            if r["kind"] == "code" and r["reference"].get("file") == name
        ]
        # Writable intervals are exactly the source ranges already supplied
        # in this selected file. No small-file shortcut may grant unread lines.
        if any(
            type(r.get("start_line")) is not int
            or type(r.get("end_line")) is not int
            or not 1 <= r["start_line"] <= r["end_line"] <= len(lines)
            for r in refs
        ):
            raise AuditError("已读源码区间无效", code="evidence_insufficient")
        ranges = sorted((r["start_line"], r["end_line"]) for r in refs)
        merged = []
        for start, end in ranges:
            if start > end:
                raise AuditError("已读源码区间无效", code="evidence_insufficient")
            if merged and start <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        segments = [
            {
                "start_line": start,
                "end_line": end,
                "content": "".join(lines[start - 1 : end]),
            }
            for start, end in merged
        ]
        if not segments:
            raise AuditError("修复目标缺少已读源码窗口", code="evidence_insufficient")
        complete = len(segments) == 1 and segments[0]["content"] == text
        contents[name] = (
            text
            if complete
            else "\n\n".join(
                f"[exact lines {s['start_line']}-{s['end_line']}; omitted source is not supplied]\n{s['content']}"
                for s in segments
            )
        )
        views[name] = {
            "complete": complete,
            "total_lines": len(lines),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "segments": segments,
        }
    return contents, views


def verify_visible_changes(changes, views):
    for change in changes:
        view = views.get(change.file)
        if (
            not view
            or not change.old_text
            or not any(change.old_text in s["content"] for s in view["segments"])
        ):
            raise AuditError("补丁旧文本必须来自本次已提供的精确源码窗口")


def supplied_evidence(row, views):
    if row["kind"] != "code":
        return False
    ref = row["reference"]
    view = views.get(ref.get("file"), {})
    return view.get("complete", False) or any(
        segment["start_line"] <= ref.get("start_line", 0)
        and segment["end_line"] >= ref.get("end_line", 10**9)
        for segment in view.get("segments", [])
    )
