"""Bounded real bootstrap/related source pages and property-specific obligations."""

import json
import re
from pathlib import Path

from app.adapters.source_inventory import inspectable
from app.services.scout_inspection import compact_pages


def property_for(target):
    hypothesis = target.get("hypothesis", {})
    if isinstance(hypothesis, dict) and hypothesis.get("security_property"):
        return hypothesis["security_property"]
    weakness = target.get("weakness") or target.get("static_alert", {}).get("tags", [])
    exact = str(weakness)
    priorities = [
        (
            r"(?:CWE-|cwe[-/])0?(?:215|256|259|321|327|328|330|338|489|614|798)(?:\D|$)",
            "secrets_config",
        ),
        (r"(?:CWE-|cwe[-/])0?(?:352|384|501)(?:\D|$)", "state_integrity"),
        (
            r"(?:CWE-|cwe[-/])0?(?:20|22|74|78|89|90|94|95|502|601|611|643|918|1336)(?:\D|$)",
            "input_injection",
        ),
        (r"(?:CWE-|cwe[-/])0?79(?:\D|$)", "output_encoding"),
        (r"(?:CWE-|cwe[-/])0?306(?:\D|$)", "authentication"),
        (r"(?:CWE-|cwe[-/])0?307(?:\D|$)", "rate_limiting"),
        (r"(?:CWE-|cwe[-/])0?778(?:\D|$)", "security_logging"),
        (r"(?:CWE-|cwe[-/])0?639(?:\D|$)", "object_ownership"),
        (r"(?:CWE-|cwe[-/])0?(?:862|863)(?:\D|$)", "authorization"),
    ]
    for pattern, prop in priorities:
        if re.search(pattern, exact, re.I):
            return prop
    text = str(weakness) + " " + str(hypothesis)
    mappings = [
        (r"CWE-0?778|security.event|security.logging", "security_logging"),
        (r"CWE-0?307|rate.limit|throttl|lockout", "rate_limiting"),
        (r"CWE-0?639|ownership|IDOR", "object_ownership"),
        (r"CWE-0?(?:862|863)|role.check|authorization", "authorization"),
        (r"CWE-0?306|authentication.guard|unauthenticated.*route", "authentication"),
        (r"CWE-0?79(?:\D|$)|XSS|unescaped|innerHTML", "output_encoding"),
        (r"CWE-0?(?:352|384)|CSRF|session", "state_integrity"),
        (r"CWE-0?(?:798|256|489)|secret|plaintext|debug", "secrets_config"),
        (r"CWE-0?(?:78|89|94|611)|injection|deserializ", "input_injection"),
    ]
    return next(
        (prop for pattern, prop in mappings if re.search(pattern, text, re.I)), "other"
    )


def bootstrap_files(evidence, current, modern=False):
    paths = [p.relative_to(evidence.root).as_posix() for p in evidence.files()]
    candidates = [
        p
        for p in paths
        if Path(p).name
        in {"server.js", "app.js", "main.js", "app.py", "main.py", "server.py"}
    ]
    candidates.sort(key=lambda p: (len(Path(p).parts), p))
    related = []
    for item in current:
        if item["kind"] != "code":
            continue
        file = item["reference"].get("file", "")
        for module in re.findall(r"require\(['\"](\.[^'\"]+)['\"]\)", item["content"]):
            path = (evidence.root / Path(file).parent / module).resolve()
            for resolved in (path, path.with_suffix(".js"), path / "index.js"):
                if resolved.is_file() and resolved.is_relative_to(evidence.root):
                    name = resolved.relative_to(evidence.root).as_posix()
                    if name in paths:
                        related.append(name)
                        break
    if modern and evidence.audit.language == "python":
        from app.adapters.local_imports import (
            python_import_paths,
            python_web_entrypoint,
        )

        allowed = set(paths)
        factories = []
        for name in paths:
            if name.endswith(".py"):
                body = evidence.allowed(name).read_text()
                if python_web_entrypoint(body):
                    factories.append(name)
        for row in current:
            if row["kind"] == "code" and row["reference"].get("file", "").endswith(
                ".py"
            ):
                related.extend(
                    python_import_paths(
                        evidence.root, row["reference"]["file"], row["content"], allowed
                    )
                )
        candidates = list(dict.fromkeys(factories + candidates))
    # Actual import/factory syntax is navigation; supplied pages establish code facts.
    return list(dict.fromkeys(candidates[:3] + related))[:7]


def augment_context(service, context):
    materials = list(context["evidence"])
    completed, gaps = [], []
    cap = min(26000, service.inputs.max_context_chars - 9000)
    modern = (
        service.stage.kind == "scout" and service.stage.prompt_version in {"7", "8"}
    ) or (
        service.stage.kind == "review" and service.stage.prompt_version in {"9", "10"}
    )
    for file in bootstrap_files(service.evidence, materials, modern=modern):
        path = service.evidence.allowed(file)
        lines = path.read_text().splitlines()
        if len(lines) > 350 or path.stat().st_size > 16000:
            gaps.append({"file": file, "reason": "module_requires_targeted_pages"})
            continue
        ranges = [
            (r["reference"].get("start_line", 0), r["reference"].get("end_line", 0))
            for r in materials
            if r["kind"] == "code" and r["reference"].get("file") == file
        ]
        if all(
            any(start <= n <= end for start, end in ranges)
            for n in range(1, len(lines) + 1)
        ):
            completed.append(file)
            continue
        proposed = materials
        for start in range(1, len(lines) + 1, 151):
            end = min(start + 150, len(lines))
            if len("\n".join(lines[start - 1 : end])) > 10000:
                gaps.append({"file": file, "reason": "page_requires_narrower_read"})
                break
            proposed = compact_pages(
                [*proposed, service.evidence.read(file, start, end)]
            )
        else:
            if len(json.dumps(proposed, ensure_ascii=False)) <= cap:
                materials = proposed
                completed.append(file)
            else:
                gaps.append({"file": file, "reason": "not_supplied_context_cap"})
    context = {
        **context,
        "evidence": materials,
        "local_control_context": {
            "provided_complete_modules": completed,
            "missing_modules": gaps,
            "meaning": "Actual bootstrap/import source. Dynamic imports and middleware mounts still need verification. Source inside this snapshot is LOCAL, not a deployment unknown.",
        },
        "security_property_contract": {
            "authentication": "Caller identity, not role/ownership permission",
            "authorization": "Required permission/role vs actual guards; login is not role permission",
            "object_ownership": "Requested resource vs caller/tenant and real guard",
            "rate_limiting": "Request chain attempt/throttle control, distinct from event recording",
            "security_logging": "Recorded security events, not UI flash/error messages",
            "state_integrity": "State-changing GET/POST, session and reset transitions; check app-level middleware",
            "proof": "Each condition separately: operation, input_or_policy, unsafe_protection. Established/contradicted premises cite actual quoted source. Missing local guards remain missing; summaries/knowledge do not substitute for code.",
        },
    }
    if "targets" in context:
        from app.services.read_tools import grounded

        context["targets"] = [
            {
                **target,
                "security_property": property_for(target),
                "required_premises": [
                    "operation",
                    "input_or_policy",
                    "unsafe_protection",
                ],
                "evidence_ids": [
                    m["id"] for m in materials if grounded([m], target["location"])
                ],
            }
            for target in context["targets"]
        ]
    if modern:
        from app.services.discovery_framework_facts import enrich_semantic_context

        context = enrich_semantic_context(
            context,
            service.inputs.max_context_chars,
            include_value_clues=(
                service.stage.kind == "scout" and service.stage.prompt_version == "8"
            )
            or (
                service.stage.kind == "review" and service.stage.prompt_version == "10"
            ),
        )
    return refresh_citation_contract(context)


def validate_premises(assessment, target, context, evidence):
    from app.adapters.operation_evidence import normalize
    from app.domain.audit import AuditError

    if assessment.security_property != target["security_property"]:
        raise AuditError("安全属性不一致；不能以认证证据替代角色或对象授权")
    checks = {p.premise: p for p in assessment.premises}
    if len(checks) != 3 or set(checks) != set(target["required_premises"]):
        raise AuditError("必要前提缺失或重复")
    for premise in assessment.premises:
        rows = evidence(premise.evidence_ids)
        if premise.status in {"established", "contradicted", "not_applicable"}:
            code = [
                r
                for r in rows
                if r["kind"] == "code"
                and inspectable(r["reference"].get("file", ""), context["language"])
            ]
            if not premise.quote or not any(
                normalize(premise.quote) in normalize(r["content"]) for r in code
            ):
                raise AuditError("前提需要实际源码引用，不能以文档或模型概括代替")
    if assessment.assessment == "supported":
        if checks["operation"].status != "established" or any(
            p.status in {"missing", "contradicted"} for p in checks.values()
        ):
            raise AuditError("未闭合本地前提不得支持漏洞")
        if (
            context.get("semantic_context_version") == 2
            and assessment.security_property
            in {
                "authentication",
                "authorization",
                "object_ownership",
                "rate_limiting",
                "security_logging",
            }
            and checks["input_or_policy"].policy_basis
            not in {"explicit_contract", "source_security_requirement"}
        ):
            raise AuditError(
                "缺少真实业务或源码政策依据；公开路由或缺失保护不能单独证明控制要求"
            )
        if assessment.security_property in {
            "authentication",
            "authorization",
            "object_ownership",
            "state_integrity",
            "rate_limiting",
            "security_logging",
        } and context.get("local_control_context", {}).get("missing_modules"):
            raise AuditError("控制链有未提供的本地源码；先定向取证或保留未决")


def refresh_control_context(service, context):
    control = context.get("local_control_context")
    if not control:
        return context
    remaining = []
    for gap in control["missing_modules"]:
        file = gap["file"]
        total = len(service.evidence.allowed(file).read_text().splitlines())
        ranges = [
            r["reference"]
            for r in context["evidence"]
            if r["kind"] == "code" and r["reference"].get("file") == file
        ]
        if not all(
            any(r["start_line"] <= n <= r["end_line"] for r in ranges)
            for n in range(1, total + 1)
        ):
            remaining.append(gap)
    return {
        **context,
        "local_control_context": {**control, "missing_modules": remaining},
    }


def refresh_citation_contract(context):
    from app.services.read_tools import grounded

    if "targets" not in context:
        return context
    targets = [
        {
            **t,
            "evidence_ids": [
                m["id"] for m in context["evidence"] if grounded([m], t["location"])
            ],
        }
        for t in context["targets"]
    ]
    return {
        **context,
        "targets": targets,
        "citation_contract": {
            **context.get("citation_contract", {}),
            "target_source_ids": {
                t["candidate_id"]: t["evidence_ids"] for t in targets
            },
        },
    }
