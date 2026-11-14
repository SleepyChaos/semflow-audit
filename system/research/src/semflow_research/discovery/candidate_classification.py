"""Model classification never creates a caller decision."""


def apply_model_classification(candidate, assessment, records):
    # Model classification is checked again by the target import/decision gate.
    # AGENT: supported is model_assessment, never a human confirmed status.
    candidate.model_assessment = assessment
