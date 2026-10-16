"""Compact navigation only; source bodies and supported facts remain verbatim."""

from copy import deepcopy


def pack_repair_payload(payload):
    packed = deepcopy(payload)
    # Retry diagnostics already carry the exact failed-check explanation.
    # Keep it once, rather than spending context again on the persisted copy.
    feedback = packed.get("failure_feedback")
    if isinstance(feedback, dict) and isinstance(feedback.get("summary"), str):
        summary = feedback["summary"]
        for check in packed.get("checks", {}).values():
            if isinstance(check, dict) and check.get("output") == summary and summary:
                check["output"] = "Exact explanation supplied in failure_feedback.summary"
    inventories = [
        packed.get("inventory"),
        packed.get("inspection", {}).get("inventory"),
    ]
    for inventory in inventories:
        if not isinstance(inventory, dict):
            continue
        files = inventory.get("files", [])
        if len(files) > 30:
            inventory["files"] = files[:30]
            inventory["navigation_omitted"] = len(files) - 30
            inventory["navigation_contract"] = (
                "Partial navigation only; use search_source/callers to locate omitted files. Omission is not evidence of absence."
            )
        if "documents" in inventory:
            inventory["documents"] = [
                {k: v for k, v in row.items() if k != "content"}
                for row in inventory["documents"]
            ]
            inventory["document_body_contract"] = (
                "Document bodies occur in evidence, not duplicated in navigation."
            )
    inspection = packed.get("inspection")
    if isinstance(inspection, dict):
        inspection.pop("inventory", None)
        # A partial writable page may already be completely present in the
        # cited inspection pages. Keep those original evidence bodies, and
        # replace only the duplicate allowed_files body by an explicit pointer.
        for name, view in packed.get("file_views", {}).items():
            if view.get("complete"):
                continue
            rows = [
                row
                for row in inspection.get("evidence", [])
                if row.get("kind") == "code"
                and row.get("reference", {}).get("file") == name
                and not row.get("content", "").startswith("See exact allowed_files")
            ]
            ranges = [
                (row["reference"]["start_line"], row["reference"]["end_line"])
                for row in rows
            ]
            if rows and all(
                all(
                    any(start <= line <= end for start, end in ranges)
                    for line in range(segment["start_line"], segment["end_line"] + 1)
                )
                for segment in view.get("segments", [])
            ):
                packed["allowed_files"][name] = (
                    "Exact source is supplied once in inspection.evidence IDs "
                    + ", ".join(row["id"] for row in rows)
                    + ". Writable old_text must remain inside one file_views segment; other supplied lines are read-only context."
                )
    return packed
