"""Algorithm extracted from app.services.review_classification.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Keep detector and model taxonomy separate; omission is not reclassification."""
import re


def known(value):
    return bool(re.fullmatch("CWE-\\d+", value or "", re.IGNORECASE))


def decision(original, reported):
    effective = reported if known(reported) else original
    return {
        "detector_weakness": original,
        "model_weakness": reported,
        "effective_weakness": effective,
        "classification_source": "model"
        if known(reported)
        else "retained_detector_hypothesis",
        "limit": "Preserved detector taxonomy is not an independently confirmed CWE label.",
    }


def implicated_cwes(target, assessment):
    values = [assessment.weakness, target.get("weakness", "")]
    hypothesis = target.get("hypothesis", {})
    if isinstance(hypothesis, dict):
        values.append(hypothesis.get("weakness", ""))
    values.extend(target.get("static_alert", {}).get("tags", []))
    return {
        int(m.group(1))
        for value in values
        for m in re.finditer("cwe[-/](\\d+)(?:$|\\b)", str(value), re.IGNORECASE)
    }
