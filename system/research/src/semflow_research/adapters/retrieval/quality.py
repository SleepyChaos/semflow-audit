"""Algorithm extracted from app.adapters.retrieval.quality.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Active source versions and explicit verification tiers, without deleting history."""


def active_records(rows, cwe=None):
    latest = {}
    for row in rows:
        key = (row.corpus_scope, row.source, row.provenance.get("corpus_origin_scope"))
        latest.setdefault(key, row.version)
    result = []
    for row in rows:
        if (
            row.version
            != latest[
                row.corpus_scope, row.source, row.provenance.get("corpus_origin_scope")
            ]
        ):
            continue
        metadata = row.provenance
        if row.corpus == "rule_example":
            validation = metadata.get("validation", {})
            if not isinstance(validation, dict) or validation.get("status") != "passed":
                continue
            if validation.get("kind") not in {
                "compile_only",
                "compiler_only",
                "official_development_test",
            }:
                continue
            identifiers = metadata.get("cwe_ids", [metadata.get("cwe")])
            if cwe and cwe not in identifiers:
                continue
        result.append(row)
    return result
