"""Plan source probes independently of the model's external-gap label."""

import re

from semflow_contracts.review_gaps import EvidenceGapRequest

_PATH = re.compile(
    r"(?<![\w/])(?:[\w-]+/)*[\w-]+\.(?:py|js|ts|jsx|tsx|toml|json|ya?ml)\b"
)
_CALL = re.compile(r"\b(?:[A-Za-z_]\w*\.)*([A-Za-z_]\w*)\s*\(")
_CONCEPTS = (
    (r"middleware|中间件", ("middleware.py",)),
    (r"decorator|装饰器", ("decorators.py",)),
    (r"schema|模式定义", ("schema.py",)),
    (r"route|routing|urlconf|路由", ("urls.py", "routes.py")),
    (r"settings|config|配置", ("settings.py", "config.py")),
    (r"permission|authori[sz]|权限|授权", ("permissions.py",)),
)


def local_probes(typed, missing):
    def path_query(path, priority="normal"):
        return EvidenceGapRequest(
            gap_type="repository",
            description=f"Inspect source for: {path}",
            target_path=path,
            suggested_action="read_source",
            priority=priority,
        )

    def symbol_query(symbol, priority="normal", action="find_symbol"):
        return EvidenceGapRequest(
            gap_type="repository",
            description=f"Resolve source reference: {symbol}",
            target_symbol=symbol,
            suggested_action=action,
            priority=priority,
        )

    for row in typed:
        if row.gap_type == "repository":
            yield row
            continue
        if row.target_path:
            yield path_query(row.target_path, row.priority)
        if row.target_symbol:
            action = (
                "find_references"
                if row.suggested_action == "find_references"
                else "find_symbol"
            )
            yield symbol_query(row.target_symbol, row.priority, action)
    text = "\n".join(
        (
            *missing,
            *(r.description for r in typed),
            *(r.required_fact for r in typed if r.required_fact),
        )
    )[:12000]
    for path in dict.fromkeys(_PATH.findall(text)):
        yield path_query(path)
    for symbol in dict.fromkeys(_CALL.findall(text)):
        if len(symbol) >= 2:
            yield symbol_query(symbol[:180])
    for concept, paths in _CONCEPTS:
        if re.search(concept, text, re.IGNORECASE):
            for path in paths:
                yield path_query(path)
