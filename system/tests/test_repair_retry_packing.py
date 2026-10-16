"""Retry context keeps exact diagnostics once without mutating durable checks."""

from copy import deepcopy

from app.adapters.semantic_packing import pack_repair_payload


def test_duplicate_retry_diagnostic_uses_existing_exact_summary():
    explanation = 'Missing actual caller source; preserve this exact diagnostic. ' * 100
    payload = {
        'failure_feedback': {'summary': explanation},
        'checks': {
            'semantic_contract': {'status': 'failed', 'output': explanation},
            'other': {'status': 'failed', 'output': 'Different failure remains intact'},
        },
    }
    original = deepcopy(payload)
    packed = pack_repair_payload(payload)
    assert payload == original
    assert packed['failure_feedback']['summary'] == explanation
    assert packed['checks']['semantic_contract']['status'] == 'failed'
    assert packed['checks']['semantic_contract']['output'] == (
        'Exact explanation supplied in failure_feedback.summary'
    )
    assert packed['checks']['other'] == original['checks']['other']
    assert pack_repair_payload(packed) == packed
