"""Materialize caller-selected immutable scan inputs for native repair rescan."""

import hashlib
from uuid import uuid5

from semflow_contracts.common import EntityRef, SourceSnapshot
from semflow_research.public.baselines import capture, input_findings
from semflow_research.public.runs import inspect
from semflow_research.public.sources import tree_digest
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError
from app.research_bridge.models import ResearchAuditBinding
from app.research_bridge.requests import research_root


def freeze(binding, audit, session, snapshot, source_root):
    scan_binding = session.exec(
        select(ResearchAuditBinding).where(ResearchAuditBinding.audit_id == audit.id)
    ).first()
    baseline = None
    if scan_binding is not None and scan_binding.request:
        receipt = inspect(scan_binding.execution_id, root=research_root())
        baseline = receipt.result.baseline if receipt and receipt.result else None
        if baseline is not None:
            original = SourceSnapshot.model_validate(scan_binding.request["source"])
            if original.tree_sha256 != snapshot.tree_sha256:
                raise AuditError("原始扫描与修复源码不同", code="integrity_error")
            snapshot = original
    producer = uuid5(binding.execution_id, "repair-inputs/1")
    if baseline is None:
        baseline = capture(
            snapshot=snapshot,
            source_root=source_root,
            directory=ArtifactStore().directory(str(audit.id)),
            root=research_root(),
            execution_id=producer,
            codeql_version=audit.codeql_version,
            query_pack=audit.query_pack,
            suite=audit.suite,
        )
        if audit.custom_rule_ids:
            from app.research_bridge.scan_requests import freeze_rule

            baseline = baseline.model_copy(
                update={
                    "supplemental_rules": tuple(
                        freeze_rule(i, audit, binding) for i in audit.custom_rule_ids
                    )
                }
            )
    if (
        baseline.snapshot_id != snapshot.snapshot_id
        or baseline.source_digest != snapshot.tree_sha256
    ):
        raise AuditError("修复静态基线不属于冻结源码", code="integrity_error")
    name, version = baseline.query_pack.split("@", 1)
    pack = audit_settings.CODEQL_PACK_PATH / name / version
    scan = {
        "build_profile": "none",
        "query_pack": {"name": name, "version": version, "digest": tree_digest(pack)},
        "suite": {
            "name": baseline.suite,
            "digest": hashlib.sha256((pack / baseline.suite).read_bytes()).hexdigest(),
        },
        "supplemental_rules": [
            r.model_dump(mode="json") for r in baseline.supplemental_rules
        ],
    }
    ref, values = input_findings(
        baseline,
        snapshot=snapshot,
        source_root=source_root,
        root=research_root(),
        execution_id=producer,
        legacy_source_digest=audit.snapshot_hash,
    )
    refs = {
        key: (
            EntityRef(execution_id=producer, entity_id=row.finding_id, bundle=ref),
            row.locations[0],
        )
        for key, row in values.items()
    }
    # Some earlier scientific projections retained the canonical raw SARIF ID;
    # accept it only through this verified counterpart to the legacy hash mapping.
    for record in values.values():
        refs[record.raw_id] = (
            EntityRef(execution_id=producer, entity_id=record.finding_id, bundle=ref),
            record.locations[0],
        )
    # WIRE-SEND:research.baseline — peer: runtime.repair_rescan.receive.
    # AGENT: freeze the original scan and exact query bytes together; changing
    # source identity, supplements or target linkage requires changing the receiver.
    return (
        snapshot,
        {"rescan": scan, "static_baseline": baseline.model_dump(mode="json")},
        refs,
    )
