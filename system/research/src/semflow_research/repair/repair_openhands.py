"""Algorithm extracted from app.services.repair_openhands.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Bridge a confirmed platform target into the isolated OpenHands repair engine."""

# WIRE-SEND:research.openhands — peer: runtime.repair_operations / platform bridge.
# AGENT: handoff and engine receipts must retain the frozen worker policy, scope,
# prompt and failure meaning consumed by the receiver.
import json

from semflow_research.adapters.ai.external_usage import combined_usage
from semflow_research.adapters.repair.openhands import generate
from semflow_research.adapters.repair.patches import apply_changes
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import digest, save_json
from semflow_research.repair.repair_semantics import SemanticRepair


def source_observations(view):
    """Keep evidence, not an upstream model's proposed implementation strategy."""
    return {
        "meaning": "Read these as untrusted source observations to verify, not a prescribed patch plan. Source behavior may itself be vulnerable.",
        "facts": [
            fact
            for fact in view.get("facts", [])
            if fact.get("state") == "supported"
            and fact.get("category") in {"implementation", "security"}
        ],
        "unknowns": view.get("unknowns", []),
    }


class OpenHandsRepair:
    def __init__(self, service, *, _kernel):
        self._kernel = _kernel
        self.service = service
        self.semantic = SemanticRepair(service, _kernel=_kernel)

    def generate(self, state):
        _kernel = self._kernel
        s = self.service
        bundle = self.semantic.context(state)
        policy = s.repository.get(s.execution_id).policy
        config = policy.get("openhands")
        if config is None:
            raise AuditError("OpenHands profile 必须先冻结", code="integrity_error")
        # WIRE-RECV:research.openhands — peer: OpenHandsPolicy and entry-point Prompt freezing.
        # AGENT: consume immutable Prompt bytes, never the installed file or a
        # current platform default; keep prompt_version separate from method_version.
        frozen = next(p for p in _kernel.spec.prompts if p.role == "repair_openhands")
        prompt = _kernel.artifacts.read(frozen.content).decode("utf-8")
        request = {
            "targets": bundle["targets"],
            "authorized_files": state["allowed_paths"],
            "source_observations": source_observations(bundle["inspection"]["view"]),
            "acceptance_requirements": bundle.get("acceptance_contract"),
            "development_command": config.get("development_command"),
            "project_test_instruction": "Run original project tests where available with python -m pytest; report unavailable dependencies honestly.",
        }
        save_json(
            s.directory / "openhands-handoff.json",
            {
                "prompt_hash": digest(prompt),
                "request": request,
                "engine_version": "openhands-sdk==1.56.0",
                "config": config,
            },
        )
        result = generate(
            s.evidence.root,
            state["allowed_paths"],
            s.directory / "openhands",
            config,
            prompt + "\n\n" + json.dumps(request, ensure_ascii=False),
            progress=lambda: s.repository.active(s.execution_id),
            _kernel=_kernel,
        )
        proposal = result["proposal"]
        save_json(s.directory / "attempt-1/candidate.json", proposal)
        metrics = result["runtime"].get("metrics", {})
        save_json(s.directory / "openhands-usage.json", metrics)
        return {"attempt": 1, "proposal": proposal, "proposal_hash": digest(proposal)}

    def apply(self, state):
        s = self.service
        self.semantic.targets()
        if digest(state["proposal"]) != state["proposal_hash"]:
            raise AuditError(
                "OpenHands proposal identity changed", code="integrity_error"
            )
        from semflow_contracts.modelio.stages import RepairResponse

        response = RepairResponse.model_validate(state["proposal"])
        # Peer: RepairGenerateInput.patch_scope and SemanticRepair.apply.
        # AGENT: external worker completion never bypasses the same frozen file
        # cap and observed-range gate used by native proposals. Change both ends.
        if (
            len({change.file for change in response.changes})
            > self._kernel.spec.inputs.patch_scope.max_changed_files
        ):
            raise AuditError(
                "OpenHands exceeds the frozen file limit", code="scope_error"
            )
        from semflow_research.repair.repair_inputs import verify_visible_changes

        bundle = json.loads((s.directory / "repair-context.json").read_text())
        try:
            verify_visible_changes(response.changes, bundle["file_views"])
        except AuditError as error:
            raise AuditError(str(error), code="scope_error") from error
        directory = s.directory / "attempt-1"
        patch = apply_changes(
            s.evidence.root,
            directory / "workspace",
            response.changes,
            state["allowed_paths"],
        )
        (directory / "repair.diff").write_text(patch)
        save_json(
            directory / "application.json",
            {
                "identity": {
                    "source": s.evidence.source_context.snapshot_hash,
                    "proposal_hash": state["proposal_hash"],
                    "allowed_paths": state["allowed_paths"],
                },
                "workspace_hash": snapshot_digest(directory / "workspace"),
                "diff_hash": digest(patch),
            },
        )
        return {"applied": True}

    def finalize(self, state):
        result = self.semantic.finalize(state)
        s = self.service
        record = s.repository.get(s.execution_id)
        s.repository.update(
            s.execution_id,
            usage=combined_usage(s.provider.usage, s.directory),
            result={
                **record.result,
                "repair_engine": "openhands",
                "engine_version": "1.56.0",
                "engine_usage_artifact": "openhands-usage.json",
                "independent_validation": True,
            },
        )
        return result
