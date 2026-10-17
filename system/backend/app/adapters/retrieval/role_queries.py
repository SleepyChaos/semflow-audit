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


def role_query(topic, title_terms, query, mode, *, lexical_only=False):
    if lexical_only and title_terms:
        # These slots already restrict the query to a named API module. Natural
        # language (especially Chinese) may share no tokens with QL declarations;
        # rank that module's actual declarations rather than returning no material.
        return (
            " ".join(title_terms)
            + " import DataFlow Node source sink isSource isSink barrier flow",
            "bm25",
        )
    if lexical_only and topic:
        return f"{query} {topic[0]} {topic[1]} import from select where", "bm25"
    if (
        topic
        and topic[1] in {"CWE-078", "CWE-022", "CWE-943"}
        and title_terms == ["ApiGraphs", "DataFlow", "TaintTracking"]
    ):
        # Vulnerability terms need not occur in a generic Node/type declaration.
        return "DataFlow Node TaintTracking source sink barrier", "bm25"
    return query, mode
