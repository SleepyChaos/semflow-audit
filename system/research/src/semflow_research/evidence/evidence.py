"""Actual source evidence and scientific records, without platform persistence."""

"Only real, scope checked snapshot evidence can be cited by a candidate."
import ast
import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.domain.errors import AuditError
from semflow_research.state.models import Evidence


class EvidenceService:
    def __init__(
        self, snapshot_id: str, execution_id: str, paths: list[str], *, _kernel
    ):
        self._kernel = _kernel
        self.source_context = _kernel.source_records.get(snapshot_id)
        self.execution_id = UUID(execution_id)
        self.root = (
            ArtifactStore(_kernel=_kernel)
            .source(str(self.source_context.snapshot_id))
            .resolve()
        )
        if snapshot_digest(self.root) != self.source_context.snapshot_hash:
            raise AuditError(
                "源码快照完整性检查失败；不能引用被改动的代码", code="integrity_error"
            )
        from semflow_research.state.models import ExecutionRecord

        with _kernel.records.transaction() as session:
            stage = session.get(ExecutionRecord, self.execution_id)
            if stage is None or stage.snapshot_id != self.source_context.id:
                raise AuditError("取证阶段不属于本次审计", code="identity_error")
        self.paths = paths
        for path in paths:
            self.target(path)

    def target(self, name: str) -> Path:
        if not name or "\\" in name or ":" in name or Path(name).is_absolute():
            raise AuditError("源码路径无效")
        from semflow_research.adapters.source_inventory import readable_name

        if not readable_name(name):
            raise AuditError("不能读取凭据或依赖工作目录")
        path = (self.root / name).resolve()
        if (
            not path.is_relative_to(self.root)
            or path.is_symlink()
            or (not path.exists())
        ):
            raise AuditError("源码位置不在本次快照中")
        return path

    def allowed(self, name: str) -> Path:
        path = self.target(name)
        # Interface peer: semflow_contracts.repair.PatchScope.
        # AGENT: an empty readable_paths means writable_paths only; retain the
        # same restriction in inventory/search/callers, not just direct reads.
        if not self.in_scope(path):
            raise AuditError("取证超出冻结的可读范围", code="scope_error")
        return path

    def in_scope(self, path: Path) -> bool:
        scope = getattr(self._kernel.spec.inputs, "patch_scope", None)
        if scope is not None:
            readable = tuple(
                dict.fromkeys([*scope.writable_paths, *scope.readable_paths])
            )
            if not any(path.is_relative_to(self.target(item)) for item in readable):
                return False
        return not self.paths or any(
            path.is_relative_to(self.target(scope)) for scope in self.paths
        )

    def files(self, expanded: bool = True) -> list[Path]:
        from semflow_research.adapters.source_inventory import inspectable

        return sorted(
            path
            for path in self.root.rglob("*")
            if path.is_file()
            and (not path.is_symlink())
            and inspectable(
                path.relative_to(self.root).as_posix(),
                self.source_context.language,
                expanded,
            )
            and self.in_scope(path)
        )

    def record(self, kind: str, content: str, reference: dict) -> dict:
        _kernel = self._kernel
        if snapshot_digest(self.root) != self.source_context.snapshot_hash:
            raise AuditError("取证过程中源码快照发生变化", code="integrity_error")
        digest = hashlib.sha256(content.encode()).hexdigest()
        evidence = Evidence(
            execution_id=self.execution_id,
            snapshot_id=self.source_context.id,
            kind=kind,
            snapshot_hash=self.source_context.snapshot_hash,
            reference=reference,
            content=content,
            digest=digest,
            provenance={"call_id": str(uuid4()), "tool": kind},
        )
        with _kernel.records.transaction() as session:
            existing = session.list(
                Evidence,
                execution_id=self.execution_id,
                snapshot_id=self.source_context.id,
                snapshot_hash=self.source_context.snapshot_hash,
                kind=kind,
                digest=digest,
            )
            same = next((row for row in existing if row.reference == reference), None)
            if same is not None:
                if same.content != content:
                    raise AuditError(
                        "已保存的重复证据内容被修改", code="integrity_error"
                    )
                evidence = same
            else:
                session.save(evidence)
                session.commit()
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

    @property
    def repository_navigation(self) -> bool:
        from semflow_research.discovery.review_gap_planner import navigation_enabled

        return navigation_enabled(self._kernel)

    def search(self, text: str, file_pattern: str | None = None) -> dict:
        if not isinstance(text, str) or not text or len(text) > 200:
            raise AuditError("搜索词长度无效", code="invalid_arguments")
        if self.repository_navigation:
            if file_pattern is not None and (
                not isinstance(file_pattern, str) or len(file_pattern) > 200
            ):
                raise AuditError("文件过滤参数无效", code="invalid_arguments")
            return self._repository_search(text, file_pattern)
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

    def _repository_search(self, text: str, file_pattern: str | None) -> dict:
        import json
        from dataclasses import asdict

        from semflow_research.adapters.repository_locator import RepositoryLocator

        result = RepositoryLocator(self.root, self.allowed).search_code(
            text, limit=40, file_pattern=file_pattern
        )
        matches = [
            dict(asdict(hit), line=hit.start_line, text=hit.content)
            for hit in result.matches
        ]
        return self.record(
            "search",
            json.dumps(matches, ensure_ascii=False),
            {
                "term": text,
                "limit": 40,
                "truncated": result.truncated,
                "file_pattern": file_pattern,
                "snapshot": self.source_context.snapshot_hash,
            },
        )

    def callers(self, symbol: str) -> dict:
        if self.source_context.language != "python":
            result = self.search(symbol + "(")
            result["semantic_limit"] = "Lexical matches only, not resolved call edges"
            return result
        matches = []
        for path in self.files():
            try:
                tree = ast.parse(path.read_text())
            except (SyntaxError, UnicodeError):
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
        terms = [
            "eval(",
            "exec(",
            "subprocess.",
            "pickle.loads",
            "execute(",
            "request.",
        ]
        if self.source_context.language == "javascript":
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
    snapshot_id: UUID, ids: list[UUID], require_code: bool = True, *, _kernel
) -> list[Evidence]:
    with _kernel.records.transaction() as session:
        rows = session.list(Evidence, snapshot_id=snapshot_id, id__in=ids)
    if len({row.id for row in rows}) != len(set(ids)):
        raise AuditError("证据不存在或属于其他审计任务")
    if require_code and (not any(row.kind in {"code", "query"} for row in rows)):
        raise AuditError("需要本次快照的源码或查询证据；知识文本不能单独确认缺陷")
    return rows
