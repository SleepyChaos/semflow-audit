"""Metadata-only diagnostic; does not overwrite frozen benchmark scores or model history."""
import hashlib
import json
from pathlib import Path

from app.services.review_classification import decision
from scripts.benchmarks.formal_scoring import score_cases

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'artifacts/research/owasp-discovery/20261007-pilot-v1'


def main():
    primary = json.loads((RUN / 'evaluation.json').read_text())
    labels = primary['scores']['D0_CodeQL']['overall']['cases']
    candidates, changed, sources = [], [], {}
    for path in sorted(RUN.glob('batch-*/review.json')):
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        output = json.loads(path.read_text())
        entries = {e['candidate_id']:e for e in output['stage']['result']['pool']['entries']}
        for row in output['candidates']:
            if row['model_assessment'] != 'supported':
                continue
            entry = entries[row['id']]
            hypothesis = entry.get('hypothesis', {})
            original = hypothesis.get('weakness', 'unknown') if isinstance(hypothesis, dict) else 'unknown'
            classification = decision(original, row['weakness'])
            candidates.append({**row, 'weakness':classification['effective_weakness']})
            if classification['effective_weakness'] != row['weakness']:
                changed.append({'candidate_id':row['id'], 'location':row['location'], **classification})
    score = score_cases(labels, candidates)
    report = {'kind':'posthoc_metadata_only_counterfactual_not_new_model_or_end_to_end_run',
              'primary_frozen_scores_unchanged':True, 'model_calls':0,
              'new_binding_gate_replayed':False,
              'limits':['No CWE equivalence remapping. Omitted classification retains only detector hypothesis.',
                        'Does not establish that newly strengthened operation-binding gate accepts every original supported verdict.',
                        'Cannot be used as new system accuracy or paper uplift.'],
              'changed_classifications':changed, 'score':score, 'input_hashes':sources}
    (RUN / 'posthoc-classification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'counts':score['counts'], 'precision':score['precision'], 'recall':score['recall'], 'f1':score['f1'], 'metadata_changes':len(changed)},indent=2))


if __name__ == '__main__':
    main()
