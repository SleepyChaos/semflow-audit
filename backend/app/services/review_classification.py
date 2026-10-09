"""Keep detector and model taxonomy separate; omission is not reclassification."""

import re


def known(value):
    return bool(re.fullmatch(r"CWE-\d+", value or "", re.I))


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
        for m in re.finditer(r"cwe[-/](\d+)(?:$|\b)", str(value), re.I)
    }
