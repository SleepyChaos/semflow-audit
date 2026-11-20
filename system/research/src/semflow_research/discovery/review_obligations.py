"""Derive scoped proof obligations and verify them independently of model claims."""

from semflow_contracts.review_gaps import EvidenceGapRequest

from semflow_research.discovery.review_local_probes import local_probes
from semflow_research.discovery.review_python_behavior import inspect_behavior

_DATAFLOW = (
    ("source", "The value is controlled across the relevant trust boundary."),
    (
        "propagation",
        "The same value reaches the operation through the claimed transformations.",
    ),
    (
        "effect",
        "The resolved operation interprets or exposes the value in the claimed way.",
    ),
    (
        "reachability",
        "The input and operation can occur on the same executable application path.",
    ),
    (
        "protection",
        "The path lacks an applicable protection that prevents the behavior.",
    ),
)
_POLICY = (
    (
        "operation",
        "The target executes the protected operation with the stated effect.",
    ),
    ("actor_boundary", "The actor and protected resource are bound as claimed."),
    (
        "applicable_policy",
        "The application's security requirement applies to this actor and resource.",
    ),
    (
        "enforcement",
        "The applicable checks are absent or ineffective on a reachable path.",
    ),
)
_CONFIG = (
    (
        "activation",
        "The application loads the relevant configuration in the reviewed context.",
    ),
    ("effect", "The configuration produces the claimed security-sensitive behavior."),
    (
        "protection",
        "No applicable higher-precedence setting or protection prevents this effect.",
    ),
)
_OTHER = (
    ("effect", "The target operation has the claimed security-sensitive effect."),
    ("applicability", "The trust or policy conditions apply to that operation."),
    ("protection", "The effect remains possible under the observed controls."),
)
_POLICY_PROPERTIES = {
    "authentication",
    "authorization",
    "object_ownership",
    "rate_limiting",
    "security_logging",
    "state_integrity",
}
_DATAFLOW_CWES = {
    "78",
    "79",
    "89",
    "90",
    "94",
    "95",
    "116",
    "352",
    "502",
    "532",
    "611",
    "643",
    "943",
    "1336",
}


def _roles(property_name, weakness):
    if (
        property_name in {"input_injection", "output_encoding"}
        or weakness in _DATAFLOW_CWES
    ):
        return _DATAFLOW
    if property_name in _POLICY_PROPERTIES:
        return _POLICY
    return _CONFIG if property_name == "secrets_config" else _OTHER


def verify_obligations(
    service, assessment, target, pages, *, control=None, require_refutation=False
):
    location = target["location"]
    claimed = target.get("weakness") or assessment.weakness or ""
    if not claimed.startswith("CWE-") or claimed in {"CWE-0", "CWE-unknown"}:
        claimed = assessment.weakness or ""
    weakness = claimed.removeprefix("CWE-").lstrip("0")
    roles = _roles(assessment.security_property, weakness)
    premise = next((p for p in assessment.premises if p.premise == "operation"), None)
    quote = premise.quote if premise and premise.evidence_ids else ""
    witness = inspect_behavior(
        service.evidence,
        location,
        pages,
        quote,
        assessment.security_property,
        f"CWE-{weakness}",
    )
    # A parsed no-op only refutes the effect of that callable, not effects in
    # surrounding expressions or unrelated policies.
    action = (
        EvidenceGapRequest(
            gap_type="repository",
            target_path=witness.target_path,
            description="Read the resolved implementation and verify its actual behavior.",
            suggested_action="read_source",
            priority="high",
        )
        if witness.target_path
        else None
    )
    explicit = getattr(assessment, "evidence_gaps", ())
    local = next(
        (
            g
            for g in local_probes(
                explicit, (*assessment.missing_premises, *assessment.runtime_unknowns)
            )
            if g.target_path or g.target_symbol
        ),
        None,
    )
    host_probes = (
        _host_paths(target, control or {})
        if assessment.assessment in {"insufficient", "supported"} or require_refutation
        else ()
    )
    if action or host_probes:
        probes = [
            *([action] if action else []),
            *assessment.evidence_gaps,
            *host_probes,
        ]
        assessment.evidence_gaps = probes[:5]
    model_roles = {
        "effect": "operation",
        "operation": "operation",
        "source": "input_or_policy",
        "actor_boundary": "input_or_policy",
        "applicable_policy": "input_or_policy",
        "protection": "unsafe_protection",
        "enforcement": "unsafe_protection",
    }
    model_premises = {p.premise: p.reason for p in assessment.premises}
    obligations = []
    for role, fact in roles:
        status = "unverified"
        proof = evidence_against = ()
        verifier = "none"
        detail = "The candidate has no independent verifier for this fact with the available evidence."
        if witness.direct_flow or role in witness.supported_roles:
            status, proof, verifier, detail = (
                "supported",
                witness.refs,
                "python_direct_flow",
                witness.detail,
            )
        elif role in {"effect", "operation"} and witness.effect == "refuted":
            status, evidence_against, verifier, detail = (
                "refuted",
                witness.refs,
                "python_local_body",
                witness.detail,
            )
        next_action = None
        if status == "unverified":
            next_action = action or local or (host_probes[0] if host_probes else None)
            if next_action is None and role in {
                "reachability",
                "activation",
                "applicable_policy",
            }:
                status = "not_automatically_verifiable"
            if next_action is None:
                next_action = EvidenceGapRequest(
                    gap_type="unresolved",
                    description=f"Independently review the evidence for {role}.",
                    required_fact=fact,
                )
        claim = (
            model_premises.get(model_roles.get(role))
            if status not in {"supported", "refuted"}
            else None
        )
        obligations.append(
            {
                "role": role,
                "security_property": assessment.security_property,
                "required_fact": f"{fact} Proposed claim: {claim}" if claim else fact,
                "status": status,
                "evidence_ids": list(proof),
                "counterevidence_ids": list(evidence_against),
                "verifier": verifier,
                "detail": detail,
                "next_action": next_action.model_dump(mode="json")
                if next_action
                else None,
            }
        )
    unsupported = assessment.assessment == "supported" and any(
        o["status"] != "supported" for o in obligations
    )
    unrefuted = (
        require_refutation
        and assessment.assessment == "excluded"
        and not any(o["status"] == "refuted" for o in obligations)
    )
    shell_mode = witness.shell_selection
    if unsupported or unrefuted:
        assessment.assessment = "insufficient"
        assessment.reason = (
            "现有源码尚未独立反驳候选的必要触发条件。"
            if unrefuted
            else "宿主确认被调用函数的已核验实现没有所称效果，其他必要条件仍待验证。"
            if any(o["status"] == "refuted" for o in obligations)
            else "源码核对显示调用采用关闭 shell 的参数设置。现有证据未证明所称的 shell 解释行为，其他参数解释风险仍待验证。"
            if shell_mode in {"default_off", "explicit_off"}
            else "源码引用已核对，当前证据仍无法独立证明报告中的关键程序行为。"
        )
        assessment.missing_premises = list(
            dict.fromkeys(
                [
                    *assessment.missing_premises,
                    *(
                        o["required_fact"]
                        for o in obligations
                        if o["status"] in {"unverified", "not_automatically_verifiable"}
                    ),
                ]
            )
        )[:12]
        example = getattr(assessment.detail, "exploitation", None)
        if example is not None:
            example.status = "missing_preconditions"
            example.example = ""
            example.steps = []
            example.expected_result = assessment.reason
        assessment.detail.title = "待核验的安全候选"
        assessment.detail.description = assessment.reason
        assessment.detail.impact = "所报告的安全影响取决于尚未核验的成立条件。"
    if assessment.assessment != "excluded":
        assessment.checked_premises = [
            obligation["detail"]
            for obligation in obligations
            if obligation["status"] == "supported"
        ][:12]
    if shell_mode is not None:
        wording = {
            "explicit_on": "The cited subprocess.run call explicitly selects shell=True.",
            "explicit_off": "The cited subprocess.run call explicitly selects shell=False.",
            "default_off": "The cited call supplies no shell keyword or keyword expansion. Under the standard subprocess.run binding its default is shell=False.",
        }
        obligations.append(
            {
                "role": "process_shell_mode",
                "security_property": assessment.security_property,
                "required_fact": "Establish the shell option selected at the observed call site.",
                "status": "supported",
                "evidence_ids": list(witness.refs),
                "counterevidence_ids": [],
                "verifier": "python_subprocess_call_option",
                "detail": wording[shell_mode]
                + " This does not prove argument interpretation, reachability, or the candidate verdict.",
                "next_action": None,
            }
        )
    return obligations


def _host_paths(target, control):
    # CodeQL dataflow locations and existing control-context gaps are navigation
    # hints. They do not certify that conditions on a reported path are feasible.
    files = [
        row["file"] for row in control.get("missing_modules", ()) if row.get("file")
    ]
    files.extend(
        point["file"]
        for flow in (target.get("static_alert") or {}).get("code_flows", ())
        for point in flow
        if point.get("file") and point["file"] != target["location"]["file"]
    )
    return tuple(
        EvidenceGapRequest(
            gap_type="repository",
            target_path=file,
            suggested_action="read_source",
            description="Read the repository source identified by the application control context or CodeQL.",
        )
        for file in list(dict.fromkeys(files))[:3]
        if len(file) <= 300
    )
