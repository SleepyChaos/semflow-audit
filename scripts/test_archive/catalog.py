"""Catalog result receipts, explicitly link reports, and preserve missing provenance."""

import hashlib
import json
import os
import re
from pathlib import Path

from .identity import evidence, sha256

PRUNE = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "db",
    "database",
    "codeql-db",
    "codeql-dbs",
    "src",
    "source",
    "source-root",
    "sources",
    "snapshots",
    "packs",
    "working",
    "vendor",
}
NAMES = {
    "report.json",
    "config.json",
    "summary.json",
    "identity.json",
    "integrity.json",
    "result.json",
    "manifest.json",
    "inputs.json",
    "runner-snapshot.json",
    "freeze.json",
    "progress.json",
    "candidate-decision.json",
    "reproduction-results.json",
    "evaluation.json",
    "scored.json",
    "root-adjudication.json",
    "full-result.json",
    "oracle-result.json",
    "full-review.json",
    "paired-12.json",
    "paired-12-scored.json",
    "scout.json",
    "review.json",
    "generation.json",
    "targeted-scout.json",
    "scores.json",
    "selection.json",
    "protocol.json",
    "usage-ledger.json",
    "repetitions.json",
    "loader-correction.json",
    "upstream-bearer-rescore.json",
}
SUPPLEMENTS = {
    "dual-engine-development": ["artifacts/benchmarks/dual-discovery-final-20261005"],
    "discovery-coverage": ["artifacts/research/discovery-coverage/20261006-v*"],
    "discovery-semantic": ["artifacts/research/discovery-semantics/20261007-v*"],
    "owasp48-final": ["artifacts/research/owasp48/20261007-evolution"],
    "rag-stabilization": [
        "artifacts/benchmarks/rag-stabilization-20261004",
        "artifacts/benchmarks/rag-stabilization-v8-20261004",
    ],
}


def selected_files(root):
    paths = set()
    for folder in ("docs/research", "benchmark-data/experiments"):
        for path in (root / folder).glob("*"):
            if path.is_file() and (
                path.name.endswith("summary.json")
                or path.name in {"failure-analysis.md", "repair-calibration-report.md"}
                or (
                    path.suffix == ".md"
                    and any(
                        s in path.stem
                        for s in ("-results", "-comparison", "generality-review")
                    )
                )
            ):
                paths.add(path)
    paths.add(root / "docs/workspace-migration-review.md")
    paths.add(root / "docs/research/supplemental-20261009-plan.md")
    paths.add(root / "docs/research/chain-completion-20261009-plan.md")
    for folder in (
        "artifacts/benchmarks",
        "artifacts/research",
        "artifacts/js-validator-verification",
        ".local-workspace/outputs",
    ):
        for directory, dirs, files in os.walk(root / folder, followlinks=False):
            dirs[:] = sorted(
                n
                for n in dirs
                if n not in PRUNE and not (Path(directory) / n).is_symlink()
            )
            for name in files:
                path = Path(directory) / name
                if path.is_symlink():
                    continue
                if (
                    name in NAMES
                    or name.endswith(("-receipt.json", "-summary.json", "-report.json"))
                    or (
                        path.is_relative_to(root / "artifacts/research/supplemental")
                        and (
                            path.suffix in {".log", ".xml", ".png"}
                            or name
                            in {
                                "input-source.tar.gz",
                                "last-dom.txt",
                                "frozen-rules.json",
                                "hidden-manifest.json",
                            }
                        )
                    )
                    or (
                        path.is_relative_to(
                            root / "artifacts/research/chain-completion"
                        )
                        and (
                            path.suffix in {".log", ".xml", ".png", ".diff", ".ql"}
                            or name in {"input-source.tar.gz", "runner-source.tar.gz"}
                            or (
                                "runtime" not in path.relative_to(root).parts
                                and path.suffix in {".sarif", ".md"}
                            )
                        )
                    )
                    or (
                        Path(directory) == root / "artifacts/research"
                        and path.suffix == ".json"
                    )
                ):
                    paths.add(path)
    paths.update((root / "artifacts").glob("*.log"))
    paths.update((root / "artifacts/competitors").glob("*-freeze.txt"))
    paths.update((root / "artifacts/competitors").glob("*-receipt.json"))
    paths.update((root / "artifacts/materials").glob("rag-corpus-v*/manifest.json"))
    return sorted(p for p in paths if p.is_file() and not p.is_symlink())


def load_record(root, path):
    relative = path.relative_to(root).as_posix()
    identity = "RES-" + hashlib.sha256(relative.encode()).hexdigest()[:16]
    obj, parse = None, "not_json"
    if path.suffix == ".json":
        try:
            obj, parse = json.loads(path.read_text()), "parsed"
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            parse = "failed:" + type(exc).__name__
    version = evidence(obj)
    state = (
        "hash_evidence"
        if version["hash_maps"]
        else ("declared_only" if version["declared"] else "unresolved")
    )
    return {
        "result_id": identity,
        "path": relative,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "parse_status": parse,
        "role": "report"
        if relative.startswith(("docs/", "benchmark-data/"))
        else "local_receipt",
        "version_status": state,
        "version_evidence": version,
        "test_version_ids": [],
        "version_receipt_ids": [],
        "related_result_ids": [],
        "run_locator": relative.rsplit("/", 1)[0],
    }, obj


def normalize_reference(value):
    """Retain workspace-relative references, including pre-migration aliases."""
    if not isinstance(value, str):
        return None
    value = value.strip().removeprefix("../../").removeprefix("../")
    for marker in ("artifacts/", ".local-workspace/"):
        offset = value.find(marker)
        if offset >= 0:
            relative = value[offset:].rstrip("/。，；：")
            if not any(p == ".." for p in Path(relative).parts):
                return relative
    return None


def references(path, obj):
    found = set()

    def walk(value):
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str):
            normalized = normalize_reference(value)
            if normalized and not any(c.isspace() for c in normalized):
                found.add(normalized)

    if path.suffix == ".md":
        for token in re.findall(
            r"(?:artifacts|\.local-workspace)/[^\s`\)\]\"，；。、（]+", path.read_text()
        ):
            walk(token)
    else:
        walk(obj)
    for stem, supplements in SUPPLEMENTS.items():
        if path.stem.startswith(stem) and path.parent.name in {
            "research",
            "experiments",
        }:
            found.update(supplements)
    return sorted(found)


def build_catalog(root):
    rows, objects = [], {}
    for path in selected_files(root):
        row, obj = load_record(root, path)
        rows.append(row)
        objects[row["path"]] = obj
    by_path = {row["path"]: row for row in rows}
    by_id = {row["result_id"]: row for row in rows}
    for row in rows:
        path = root / row["path"]
        # The nearest receipt only: sibling runs or current environment never fill gaps.
        for ancestor in path.parents:
            if (
                ancestor
                in {
                    root,
                    root / "artifacts",
                    root / "artifacts/research",
                    root / "artifacts/benchmarks",
                }
                or root not in ancestor.parents
            ):
                break
            candidates = [
                ancestor / "config.json",
                ancestor / "manifest.json",
                ancestor / "identity.json",
            ]
            receipts = [
                by_path[p.relative_to(root).as_posix()]["result_id"]
                for p in candidates
                if p.relative_to(root).as_posix() in by_path and p != path
            ]
            if receipts:
                row["version_receipt_ids"] = receipts
                break
        linked = set()
        missing = []
        for reference in references(path, objects[row["path"]]):
            matches = (
                list(root.glob(reference)) if "*" in reference else [root / reference]
            )
            existing = [p for p in matches if p.exists()]
            for target in existing:
                relative = target.relative_to(root).as_posix()
                linked.update(
                    r["result_id"]
                    for r in rows
                    if r["path"] == relative
                    or (target.is_dir() and r["path"].startswith(relative + "/"))
                )
            if not existing:
                missing.append(reference)
        linked.discard(row["result_id"])
        if row["role"] == "report":
            stem = re.sub(r"-(?:results|comparison|summary)$", "", path.stem)
            for suffix in ("-results.md", "-comparison.md", "-summary.json"):
                key = (path.parent / (stem + suffix)).relative_to(root).as_posix()
                if key in by_path and key != row["path"]:
                    linked.add(by_path[key]["result_id"])
        row["related_result_ids"] = sorted(linked)
        row["missing_references"] = missing
    for row in rows:
        evidence_ids = {
            row["result_id"],
            *row["version_receipt_ids"],
            *row["related_result_ids"],
        }
        for result_id in evidence_ids.copy():
            evidence_ids.update(by_id[result_id]["version_receipt_ids"])
            evidence_ids.update(by_id[result_id]["related_result_ids"])
        row["test_version_ids"] = sorted(
            {
                "VER-" + by_id[result_id]["sha256"][:16]
                for result_id in evidence_ids
                if by_id[result_id]["version_status"] == "hash_evidence"
            }
        )
    return rows


def render_index(archive_id, rows):
    states = {
        "hash_evidence": "保存内容哈希证据",
        "declared_only": "仅声明版本",
        "unresolved": "缺版本声明",
    }
    lines = [
        "# 测试结果逐文件索引",
        "",
        f"归档 ID：`{archive_id}`。由归档脚本生成。",
        "",
        "结果 ID 固定标识原路径；每次内容以 SHA-256 标识。版本收据 ID 可在同目录 registry.json 查找。",
        "近邻配置只绑定同批次；关联结果可以是复用/诊断，不能自动当成有效成绩或同一版本。",
        "声明版本及源码哈希均保留原字段路径；缺环境/输入/评分身份不宣称完整可复现。",
        "",
        "## 文档与机器汇总",
        "",
        "| 结果 ID | 文件 | 内容 SHA-256（前12位） | 自身版本证据 | 关联内容版本 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row["role"] == "report":
            lines.append(
                f"| `{row['result_id']}` | [{row['path']}](../../../{row['path']}) | "
                f"`{row['sha256'][:12]}` | {states[row['version_status']]} | "
                f"{', '.join(row['test_version_ids']) or '仅声明或无法完整追溯，见 registry'} |"
            )
    lines += [
        "",
        "## 本地原始收据",
        "",
        "仅归档元数据和身份；完整内容位于忽略目录中的本地副本。",
        "",
        "| 结果 ID | 原路径 | 内容 SHA-256（前12位） | 自身版本证据 | 同批版本收据 ID |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row["role"] == "local_receipt":
            lines.append(
                f"| `{row['result_id']}` | `{row['path']}` | `{row['sha256'][:12]}` | "
                f"{states[row['version_status']]} | {', '.join(row['version_receipt_ids']) or '缺失'} |"
            )
    return "\n".join(lines) + "\n"


def render_versions(archive_id, versions):
    lines = [
        "# 历史内容版本收据",
        "",
        f"归档 ID：`{archive_id}`。",
        "",
        "VER 标识收据文件的不可变内容；同一批次可能有多个配置/Prompt/源码收据。",
        "不把语料或 Prompt 哈希当完整实现版本；具体证据类型在表中列出，完整字段在 registry.json。",
        "",
        "| 版本 ID | 收据路径 | 内容哈希证据类型 | 直接声明 |",
        "| --- | --- | --- | --- |",
    ]
    for version in versions:
        identity = version["evidence"]
        declared = {
            k: v
            for k, v in identity["declared"].items()
            if k
            in {
                "experiment_id",
                "run_id",
                "git_head",
                "version",
                "scout_version",
                "review_version",
            }
            or k.startswith("prompt_versions.")
        }
        lines.append(
            f"| `{version['version_id']}` | `{version['evidence_path']}` | "
            f"{', '.join(identity['hash_maps'])} | {json.dumps(declared, ensure_ascii=False)} |"
        )
    return "\n".join(lines) + "\n"
