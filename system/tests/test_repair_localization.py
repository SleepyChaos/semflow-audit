from copy import deepcopy
from types import SimpleNamespace

from app.services.repair_localization import fields, localized_repair


def test_translation_changes_reason_only_and_is_bound_to_its_original_text():
    record = {
        "id": "repair-id",
        "changes": [
            {
                "file": "app.py",
                "old_text": "raw()",
                "new_text": "escape(raw())",
                "reason": "Escape the untrusted output before rendering.",
            }
        ],
        "status": "needs_review",
    }
    before = deepcopy(record)
    key = fields(record)[0]["key"]
    jobs = [
        SimpleNamespace(
            result={"translations": {key: "渲染前转义不可信输出。"}}, status="completed"
        )
    ]
    translated = localized_repair(record, jobs)
    assert translated["changes"][0]["reason"] == "渲染前转义不可信输出。"
    assert translated["changes"][0]["old_text"] == record["changes"][0]["old_text"]
    assert translated["changes"][0]["new_text"] == record["changes"][0]["new_text"]
    assert translated["status"] == "needs_review"
    assert record == before
    record["changes"][0]["reason"] = "A new and different explanation."
    assert localized_repair(record, jobs)["needs_localization"]
