"""Pinned non-core operation names and lexical queries for generic API roles."""


def refined_slots(language, topic, slots):
    # Eval/SQL/XSS slots stay exactly as frozen in the matched experiment.
    if not topic or topic[1] not in {"CWE-078", "CWE-022", "CWE-943"}:
        return slots
    result = list(slots)
    actual = {
        ("javascript", "CWE-022"): "TaintedPath",
        ("python", "CWE-943"): "NoSqlInjection",
    }.get((language, topic[1]), topic[0])
    result[0] = ("reference", 1, [" " + actual + "Query API"], None)
    result[1] = ("reference", 1, [" " + actual + "Customizations API"], None)
    return result


def role_query(topic, title_terms, query, mode):
    if (
        topic
        and topic[1] in {"CWE-078", "CWE-022", "CWE-943"}
        and title_terms == ["ApiGraphs", "DataFlow", "TaintTracking"]
    ):
        # Vulnerability terms need not occur in a generic Node/type declaration.
        return "DataFlow Node TaintTracking source sink barrier", "bm25"
    return query, mode
