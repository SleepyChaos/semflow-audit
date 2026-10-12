"""Active source versions and explicit verification tiers, without deleting history."""


def active_records(rows, cwe=None):
    latest = {}
    for row in rows:
        # Input is newest first. Select current source version before eligibility so a
        # failed replacement cannot silently resurrect an older apparently valid one.
        key = (row.owner_id, row.source)
        latest.setdefault(key, row.version)
    result = []
    for row in rows:
        if row.version != latest[(row.owner_id, row.source)]:
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
