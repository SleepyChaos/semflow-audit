"""Standalone JSON Schema declarations for exchanged payloads and their bodies."""

from types import MappingProxyType

from semflow_contracts.actions import ApprovalDecision, ApprovalRequest, ControlCommand
from semflow_contracts.baselines import StaticBaseline
from semflow_contracts.bundles import (
    AssessmentBundle,
    BundleIndex,
    CandidateBundle,
    DecisionBundle,
    EvidenceBundle,
    StaticFindingBundle,
)
from semflow_contracts.checkpoints import CheckpointBundle
from semflow_contracts.common import SourceManifest, SourceSnapshot
from semflow_contracts.corpus import CorpusManifest
from semflow_contracts.discovery_trace import DiscoveryTrace
from semflow_contracts.events import ExecutionEvent
from semflow_contracts.openhands import OpenHandsReceipt
from semflow_contracts.repair import OpenHandsPolicy, RepairAttempts
from semflow_contracts.results import ResultEnvelope
from semflow_contracts.rules import RuleDiagnostics
from semflow_contracts.runs import RUN_ADAPTER
from semflow_contracts.scout_continuation import ScoutContinuation
from semflow_contracts.suites import FrozenSuite
from semflow_contracts.toolchains import RuleToolchain

SCHEMAS = MappingProxyType(
    {
        "run": RUN_ADAPTER.json_schema,
        "result": ResultEnvelope.model_json_schema,
        "event": ExecutionEvent.model_json_schema,
        **{
            name: model.model_json_schema
            for name, model in {
                "candidate_bundle": CandidateBundle,
                "evidence_bundle": EvidenceBundle,
                "assessment_bundle": AssessmentBundle,
                "decision_bundle": DecisionBundle,
                "static_finding_bundle": StaticFindingBundle,
                "bundle_index": BundleIndex,
                "corpus_manifest": CorpusManifest,
                "rule_toolchain": RuleToolchain,
                "static_baseline": StaticBaseline,
                "discovery_trace": DiscoveryTrace,
                "scout_continuation": ScoutContinuation,
                "approval_request": ApprovalRequest,
                "approval_decision": ApprovalDecision,
                "control": ControlCommand,
                "checkpoint": CheckpointBundle,
                "repair_attempts": RepairAttempts,
                "rule_diagnostics": RuleDiagnostics,
                "openhands_policy": OpenHandsPolicy,
                "openhands_receipt": OpenHandsReceipt,
                "repair_suite": FrozenSuite,
                "source_manifest": SourceManifest,
                "source_snapshot": SourceSnapshot,
            }.items()
        },
    }
)
