"""Receive kernel receipts only against their frozen platform execution binding."""

from semflow_contracts.common import digest
from semflow_contracts.results import ResultEnvelope
from semflow_contracts.runs import validate_spec
from semflow_research.public.runs import inspect

from app.adapters.artifacts import ArtifactStore
from app.adapters.snapshot import snapshot_digest
from app.domain.audit import AuditError
from app.research_bridge.requests import research_root


def verify_receipt(binding, audit, result):
    # WIRE-RECV:research.result — peers: execution.execute and requests.freeze_stage.
    # AGENT: input identity, exact published receipt, and the verified conversion
    # between the two source hash formats are one boundary. Do not project a UI
    # status or changed binding in place of the saved scientific result.
    result = ResultEnvelope.model_validate_json(result.model_dump_json())
    spec = validate_spec(binding.request)
    # Peer: LocalLedger._store. Historical bindings hash the JSON actually
    # frozen, not newly expanded optional defaults; readonly projection must not
    # rewrite history. Executing/resuming still requires the original spec/code.
    if (
        result.execution_id != binding.execution_id
        or result.input_digest != digest(binding.request)
        or result.module != spec.module
        or result.operation != spec.operation
    ):
        raise AuditError("科研结果不属于平台冻结请求", code="identity_error")
    if (
        result.manifest is None
        or inspect(result.execution_id, root=research_root()) != result
    ):
        raise AuditError("只能投影已发布且核验一致的科研清单", code="integrity_error")
    if (
        audit.snapshot_hash != binding.legacy_source_digest
        or snapshot_digest(ArtifactStore().source(str(audit.source_run_id)))
        != binding.legacy_source_digest
    ):
        raise AuditError(
            "平台原始源码已变化，科研结果保留但不能关联到变动后的源码",
            code="integrity_error",
        )
    return result
