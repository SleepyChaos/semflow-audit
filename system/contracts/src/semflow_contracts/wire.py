"""Versioned meanings for JSON exchanged between independently owned components.

AGENT CONSTRAINT: change the schema, producer and consumer together when changing
meaning. WIRE-SEND/WIRE-RECV comments identify the peer sites; they are checked by
tests and deliberately live outside ordinary JSON payloads.
"""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class WireMeaning:
    contract_id: str
    schema_version: str
    semantics_revision: int
    meaning: str


MEANINGS = MappingProxyType(
    {
        "run": WireMeaning(
            "research.run",
            "semflow.research.run/1.0",
            8,
            "Execution ID is a research identity, not a platform stage ID. Inputs, source, prompts and policy are frozen; repair initial/total source reads, candidate attempts and method model-call caps are distinct; validation is structural before evidence is checked.",
        ),
        "result": WireMeaning(
            "research.result",
            "semflow.research.result/1.0",
            4,
            "Execution status, completeness and validation are independent. Completed does not mean confirmed, accepted or published. Failed is never successful empty findings.",
        ),
        "manifest": WireMeaning(
            "research.manifest",
            "semflow.research.manifest/1.0",
            1,
            "Immutable revision binds exact spec/result bytes. Digests are byte identities; the manifest reference is omitted from result bytes to avoid a hash cycle.",
        ),
        "evidence": WireMeaning(
            "research.evidence",
            "semflow.research.evidence/1.0",
            2,
            "Code excerpts are UTF-8 logical lines joined with LF and no terminal newline; file hashes cover the original bytes. Evidence belongs to one source snapshot and producing execution. A valid structure cannot substitute for real source bytes, ranges and authorized upstream references.",
        ),
        "event": WireMeaning(
            "research.event",
            "semflow.research.event/1.0",
            1,
            "Events are append-only observations with monotonic per-execution sequence. Event delivery may repeat; final facts are reconstructed from verified manifests.",
        ),
        "approval": WireMeaning(
            "research.approval",
            "semflow.research.approval/1.0",
            2,
            "Approval binds a human action to exact frozen subject bytes and checkpoint; its subject digest hashes canonical JSON for the ordered full ArtifactRef list; it does not approve modified content or establish correctness.",
        ),
        "control": WireMeaning(
            "research.control",
            "semflow.research.control/1.0",
            1,
            "Resume keeps the execution identity and requires matching approval, checkpoint and revision. Retry is a new execution. Cancellation requests do not imply an external command has stopped.",
        ),
        "checkpoint": WireMeaning(
            "research.checkpoint",
            "semflow.langgraph-containers/1",
            1,
            "Serialized native framework byte containers are bound to one execution, exact input digest and pinned engine. They never grant approval or select different inputs.",
        ),
        "model_exchange": WireMeaning(
            "research.model_exchange",
            "semflow.model-response/1",
            1,
            "Frozen prompts and schemas constrain structured model output; structural validity is not evidence validity or human approval. Persist a reservation before sending; unknown outcomes must not be replayed.",
        ),
        "source": WireMeaning(
            "research.source",
            "semflow.source-tree/1",
            1,
            "Source tree identity is SHA-256 of the canonical SourceManifest JSON. Archive entries must match every frozen path and file digest; legacy platform tree digests require an explicit verified conversion.",
        ),
        "bundle": WireMeaning(
            "research.bundle",
            "semflow.research.bundle/1",
            2,
            "A bundle is a typed set of uniquely identified entities from its declared producing execution and source snapshot. Selection cannot name missing entities; nested artifact access must be explicitly validated.",
        ),
        "resources": WireMeaning(
            "research.resources",
            "semflow.tool-resources/1",
            2,
            "An execution records the exact non-secret resolved resource profile; the same execution cannot resume with different endpoints, tool paths, images or limits. Credentials are resolved separately and excluded from persisted JSON.",
        ),
        "bundle_index": WireMeaning(
            "research.bundle_index",
            "semflow.research.bundle-index/1",
            1,
            "A coordinator indexes immutable member bundles without changing their producers or entity identities. Readers verify the full index chain, selected membership and snapshot; index ownership grants no implicit access to unrelated scientific records.",
        ),
        "openhands": WireMeaning(
            "research.openhands",
            "semflow.openhands-policy/1",
            1,
            "Frozen SDK, image, model, endpoint, prompt and execution limits are consumed by the external worker without live defaults. Worker completion produces only a candidate; failure, timeout and cancellation preserve receipts and never imply patch acceptance.",
        ),
        "openhands_receipt": WireMeaning(
            "research.openhands_receipt",
            "semflow.openhands-receipt/1",
            1,
            "Immutable worker status and member byte references survive workspace deletion, failure and cancellation. Worker completion is independent of validation and acceptance; unknown calls remain charged in the execution journal.",
        ),
        "repair_suite": WireMeaning(
            "research.repair_suite",
            "semflow.repair-suite/1",
            1,
            "Frozen executable assertions bind exact source, target refs, files and image. Generation requires caller review; execution is technical evidence, never human acceptance. Target rebinding preserves original provenance and assertion bytes.",
        ),
        "repair_attempts": WireMeaning(
            "research.repair_attempts",
            "semflow.repair-attempts/1",
            2,
            "Each attempt retains its original ordinal, exact context/proposal/patch artifacts and executed checks. Selection is a scientific output, not acceptance; omitted or unexecuted checks cannot be promoted to passed.",
        ),
        "corpus": WireMeaning(
            "research.corpus",
            "semflow.research.corpus/1",
            2,
            "Frozen corpus membership, complete chunk bytes, collection/version/validation provenance and vector identity are immutable inputs; no live platform visibility or latest-version lookup may replace them.",
        ),
        "rule_toolchain": WireMeaning(
            "research.rule_toolchain",
            "semflow.rule-toolchain/1",
            1,
            "The actual CodeQL version, installed query pack and complete dependency source closure must match before generation or resumed validation; a named profile is not a byte identity.",
        ),
        "rule_diagnostics": WireMeaning(
            "research.rule_diagnostics",
            "semflow.rule-diagnostics/1",
            1,
            "Rule compilation, development, replay and generation diagnostics are immutable member references. They preserve failures and partial work; diagnostics never grant approval or publication.",
        ),
        "baseline": WireMeaning(
            "research.baseline",
            "semflow.codeql-baseline/1",
            1,
            "An immutable archive of the actual CodeQL database and SARIF is bound to its source snapshot, tool version and original source prefix. Downstream queries use a separate working copy; missing input is not an empty successful scan.",
        ),
        "scout_continuation": WireMeaning(
            "research.scout_continuation",
            "semflow.scout-continuation/1",
            1,
            "A new execution continues only pending windows of an exact immutable scout map and source. Original candidate/evidence producers and completed units remain unchanged; additional work has its own execution and budget.",
        ),
    }
)


def schema_meaning(name: str) -> dict:
    value = MEANINGS[name]
    return {
        "$comment": (
            f"WIRE {value.contract_id}; semantics revision {value.semantics_revision}. "
            f"{value.meaning} AGENT: inspect both WIRE-SEND and WIRE-RECV sites and "
            "compatibility tests before changing this contract; update the semantic "
            "revision or major version when meaning changes."
        ),
        "x-semflow-contract": value.contract_id,
        "x-semflow-schema-version": value.schema_version,
        "x-semflow-semantics-revision": value.semantics_revision,
    }
