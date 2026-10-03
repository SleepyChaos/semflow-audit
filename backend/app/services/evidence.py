"""Only real, scope checked snapshot evidence can be cited by a candidate."""

import ast
import hashlib
from pathlib import Path
from uuid import UUID

from sqlmodel import Session, select

from app.adapters.artifacts import ArtifactStore
from app.adapters.snapshot import snapshot_digest
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_repository import AuditRepository
from app.persistence.stage_models import Evidence


class EvidenceService:
    def __init__(self, audit_id: str, stage_id: str, paths: list[str]):
        self.audit = AuditRepository().get(audit_id)
        self.stage_id = UUID(stage_id)
        self.root = ArtifactStore().source(str(self.audit.source_run_id)).resolve()
        if snapshot_digest(self.root) != self.audit.snapshot_hash:
            raise AuditError("源码快照完整性检查失败；不能引用被改动的代码")
        self.paths = paths
        for path in paths:
            self.target(path)

    def target(self, name: str) -> Path:
        if not name or "\\" in name or ":" in name:
            raise AuditError("源码路径无效")
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root) or path.is_symlink() or not path.exists():
            raise AuditError("源码位置不在本次快照中")
        return path

    def allowed(self, name: str) -> Path:
        path = self.target(name)
        if self.paths and not any(
            path.is_relative_to(self.target(scope)) for scope in self.paths
        ):
            raise AuditError("取证请求超出已选择范围")
        return path

    def files(self) -> list[Path]:
        suffixes = (
            {".py"}
            if self.audit.language == "python"
            else {".js", ".jsx", ".ts", ".tsx"}
        )
        return sorted(
            path
            for path in self.root.rglob("*")
            if path.is_file()
            and path.suffix in suffixes
            and (
                not self.paths
                or any(path.is_relative_to(self.target(scope)) for scope in self.paths)
            )
        )

    def record(self, kind: str, content: str, reference: dict) -> dict:
        if snapshot_digest(self.root) != self.audit.snapshot_hash:
            raise AuditError("取证过程中源码快照发生变化")
        digest = hashlib.sha256(content.encode()).hexdigest()
        evidence = Evidence(
            stage_id=self.stage_id,
            audit_id=self.audit.id,
            kind=kind,
            snapshot_hash=self.audit.snapshot_hash,
            reference=reference,
            content=content,
            digest=digest,
        )
        with Session(engine) as session:
            existing = session.exec(
                select(Evidence).where(
                    Evidence.stage_id == self.stage_id,
                    Evidence.audit_id == self.audit.id,
                    Evidence.snapshot_hash == self.audit.snapshot_hash,
                    Evidence.kind == kind,
                    Evidence.digest == digest,
                )
            ).all()
            same = next((row for row in existing if row.reference == reference), None)
            if same is not None:
                if same.content != content:
                    raise AuditError("已保存的重复证据内容被修改")
                evidence = same
            else:
                session.add(evidence)
                session.commit()
                session.refresh(evidence)
        return {
            "id": str(evidence.id),
            "kind": kind,
            "reference": reference,
            "content": content,
            "digest": evidence.digest,
        }

    def read(self, file: str, start_line: int = 1, end_line: int = 60) -> dict:
        path = self.allowed(file)
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise AuditError("取证文件不是可读取的小型源码")
        if start_line < 1 or end_line < start_line or end_line - start_line > 150:
            raise AuditError("源码取证窗口无效或超过 151 行")
        try:
            lines = path.read_text().splitlines()
        except UnicodeError as exc:
            raise AuditError("源码非 UTF-8 文本") from exc
        if start_line > len(lines):
            raise AuditError("源码引用行超出文件范围")
        end_line = min(end_line, len(lines))
        content = "\n".join(lines[start_line - 1 : end_line])
        if len(content) > 12000:
            raise AuditError("源码窗口过大，请缩小取证范围")
        return self.record(
            "code",
            content,
            {
                "file": path.relative_to(self.root).as_posix(),
                "start_line": start_line,
                "end_line": end_line,
            },
        )

    def search(self, text: str) -> dict:
        if not text or len(text) > 200:
            raise AuditError("搜索词长度无效")
        matches = []
        for path in self.files():
            if path.stat().st_size > 1024 * 1024:
                continue
            try:
                for number, line in enumerate(path.read_text().splitlines(), 1):
                    if text in line:
                        matches.append(
                            {
                                "file": path.relative_to(self.root).as_posix(),
                                "line": number,
                                "text": line[:500],
                            }
                        )
                    if len(matches) >= 40:
                        break
            except UnicodeError:
                continue
            if len(matches) >= 40:
                break
        import json

        return self.record(
            "search",
            json.dumps(matches, ensure_ascii=False),
            {"term": text, "limit": 40},
        )

    def callers(self, symbol: str) -> dict:
        if self.audit.language != "python":
            result = self.search(symbol + "(")
            result["semantic_limit"] = "Lexical matches only, not resolved call edges"
            return result
        matches = []
        for path in self.files():
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError, UnicodeError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = ast.unparse(node.func)
                    if name == symbol or name.endswith("." + symbol):
                        matches.append(
                            {
                                "file": path.relative_to(self.root).as_posix(),
                                "line": node.lineno,
                                "callee": name,
                            }
                        )
        import json

        return self.record(
            "callers",
            json.dumps(matches[:40]),
            {
                "symbol": symbol,
                "semantic_limit": "Syntactic Python call sites, not resolved dispatch",
            },
        )

    def anchors(self) -> list[dict]:
        # Security operations are review entry points, never a vulnerability count.
        terms = [
            "eval(",
            "exec(",
            "subprocess.",
            "pickle.loads",
            "execute(",
            "request.",
        ]
        if self.audit.language == "javascript":
            terms = ["eval(", "exec(", "innerHTML", "query(", "req.", "readFile("]
        anchors = []
        for path in self.files():
            if path.stat().st_size > 1024 * 1024:
                continue
            try:
                lines = path.read_text().splitlines()
            except UnicodeError:
                continue
            for number, line in enumerate(lines, 1):
                if any(term in line for term in terms):
                    anchors.append(
                        {
                            "id": f"{path.relative_to(self.root).as_posix()}:{number}",
                            "file": path.relative_to(self.root).as_posix(),
                            "line": number,
                            "operation": line[:300],
                            "meaning": "review_anchor_not_finding",
                        }
                    )
                    if len(anchors) >= 30:
                        return anchors
        return anchors


def valid_evidence(
    audit_id: UUID, ids: list[UUID], require_code: bool = True
) -> list[Evidence]:
    with Session(engine) as session:
        rows = session.exec(
            select(Evidence).where(Evidence.audit_id == audit_id, Evidence.id.in_(ids))
        ).all()
    if len({row.id for row in rows}) != len(set(ids)):
        raise AuditError("证据不存在或属于其他审计任务")
    if require_code and not any(row.kind in {"code", "query"} for row in rows):
        raise AuditError("需要本次快照的源码或查询证据；知识文本不能单独确认缺陷")
    return rows
