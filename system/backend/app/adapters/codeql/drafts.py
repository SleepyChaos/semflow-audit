"""Read durable generated queries, including candidates that failed validation."""

import hashlib
import json
from pathlib import Path

from app.contracts.stages import RuleResponse
from app.domain.audit import AuditError


def read_rule_drafts(directory: Path) -> list[dict]:
    drafts = []
    for attempt in range(2):
        pack = directory / f"draft-{attempt}"
        candidate = pack / "candidate.json"
        receipt = pack / "generation-receipt.json"
        if not candidate.is_file() or not receipt.is_file():
            continue
        raw = candidate.read_bytes()
        if (
            hashlib.sha256(raw).hexdigest()
            != json.loads(receipt.read_text())["candidate_digest"]
        ):
            raise AuditError("规则草稿摘要不匹配，不能展示为原始生成结果")
        response = RuleResponse.model_validate_json(raw)
        diagnostic = pack / "diagnostic.json"
        drafts.append(
            {
                "attempt": attempt + 1,
                "query": response.query,
                "modules": response.modules,
                "diagnostic": json.loads(diagnostic.read_text())
                if diagnostic.exists()
                else None,
            }
        )
    return list(reversed(drafts))
