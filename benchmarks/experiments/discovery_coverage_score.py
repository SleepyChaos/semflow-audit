"""Explicit provisional root matching for development coverage retest; no model calls."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / 'artifacts/research/discovery-coverage'
FINAL = RUNS / '20261006-v5'
OUTPUT = RUNS / '20261006-v6'
OLD = ROOT / 'artifacts/research/formal/20261005-calibration-v1'

# Primary security conditions checked against immutable source. Bundled secondary
# conditions are not granted extra roots. These are evaluator-only associations.
ASSOCIATIONS = {
    'rv-flask': {
        '001': 'abeb1163-e80e-48fb-bcb0-d289678e4ee8 db3a8979-807c-451b-b571-ac0cd4c39aff',
        '002': '97c4a814-cecd-40d2-927a-9a0c13afcad0',
        '003': 'c7a27427-776b-4914-8cbc-e7824f3b8b23',
        '005': '794742ea-0ec8-4e7f-b9a1-c44d225c4232 0c89ca98-0631-4020-bcaf-e6e4172331c1',
        '007': 'c6a93c7c-79e5-40c8-a399-11a3f3054c47 835c3bcd-fbd8-4543-b734-87f69750d115 8c27d7a0-3a17-4d4a-9f55-50a265d687de',
        '008': '85bffdcc-b313-420e-9176-9d2f00f71e46',
        '009': 'b9bc362f-dd52-4e47-bf19-420f4b5451f8 b89e3c56-54a9-471e-8dba-9939884f68eb',
        '010': '06717163-3525-4a99-aecf-4c1d658e1a1f',
        '011': 'fc9cb4b1-951e-4d46-9f45-4a941a67ac06',
        '015': 'ecb7bd39-b6f4-460a-9947-69a065f9e1c3',
        'fp-002': '4c7983a1-80cd-45c0-8455-a323ee5d28e7',
        'fp-003': 'c2a782b3-e310-48c6-a4b4-26bb161f0c72',
    },
    'rv-dvna': {
        '001': '199ad1e5-5350-40fc-b984-4defc7f83138 5d7b3f0a-2237-4258-a710-e1d7c4c61b66',
        '002': '6af11182-f3ad-40e4-a847-64dbb3a00a4d 258430dc-d0d8-4c16-9de7-91a3235044e4',
        '003': '1a019cdd-91a5-4f9a-ba75-2f6f58b3c672 905200ed-8267-4607-8b27-e26555cbb679',
        '004': '102f07b8-85f8-4636-bb3d-4324ec00e1bf 768988da-46da-4518-8199-5ef55e4f3213',
        '005': '4f584d9b-d3f8-4f6b-8aa3-7a7c80556e1c 7b51aab5-21c2-4fb6-b3b1-116a392315a6',
        '006': 'e87c3a70-c090-4dc4-873a-07f259bb62dc b77516ac-4ba6-404a-b2d5-190048aa36e8',
        '007': '53738d63-d4ba-486f-b14f-7a973ce38db0',
        '008': 'd8358270-eddd-444a-8880-c8496dcaa816 6e501c92-d09f-4f6b-bcca-c65e17f12ffe 2708663e-6b9d-4978-9a78-ce8d439f451b',
        '010': 'd4dbb13e-bcd8-4647-9ed0-69cd3c792329 5a459ea1-abfe-4e7e-be4f-3d15fddbaa01 1066652e-701c-4987-971b-acc4a319f88a 126ad11e-11c6-49b6-af62-0a21d773337f',
        '012': 'ab5823f5-6962-451d-9004-89ff54d294e7',
        '013': '661689e5-cd68-461b-99a0-abc7e89a38ef 731c8ced-6692-47b3-8ba7-f05bb5a56962',
        '015': 'ddf7a168-a781-451b-96b6-55a806a40f84',
        '016': '4d6ff7e2-a59c-4db6-8328-b6b21308ed39',
        '017': 'fac8992e-396b-43e7-9254-dbb3ab6c5c44',
    },
}
REASONS = {
    'rv-flask': {
        '002': 'evaluate returns eval(user expression) embedded in an HTML response at app.py:120; distinct from code execution, primary endpoint only.',
        '008': 'sayhi returns request-controlled template text through render_template_string at 191/205; multiple endpoint XSS hypothesis counts only its primary sayhi condition.',
        '011': 'Independent debug=True candidate at app.py:208; secondary mention in secret-key hypothesis not counted.',
        '015': 'sayhi route at 186 has no auth guard; same guarded dashboard compared with open sensitive route, no deployment reachability claim.',
        'fp-002': 'error.html:20 uses default escaped Jinja expression; no safe marker or custom autoescape override found. Model abstention retained.',
        'fp-003': 'index.html:9 default Jinja expression; undefined data and autoescape are counterevidence, no supported template XSS.',
    },
    'rv-dvna': {
        '003': 'userEditSubmit uses req.body.id in db.User.find at appHandler:145-148 then user.save:175, route has login but no ownership check. Scout primary line137 belongs to GET handler and is inaccurate; actual described operation verified separately.',
        '010': 'GET /admin/usersapi at routes/app:42 has only isAuthenticated; listUsersAPI:206-209 returns all users, not role gated. Model primary lines are sometimes inaccurate; root association uses named operation and real source.',
        '012': 'POST /login at main:51-55 binds passport login without rate limit/lockout; candidate explicitly names this endpoint. It does not grant the separate security logging root.',
        '015': 'adminusers.ejs:40-42 assigns API user fields to innerHTML; API returns persisted user fields from appHandler:206-209, register/user-edit supplies those fields. While loop off-by-one remains a separate bug, no exploit execution.',
        '016': 'products.ejs:20 raw EJS <%- output.searchTerm %> from productSearch; same suite now has js/xss after previously omitted templates were restored.',
        '017': 'products.ejs:50 raw EJS output.products[i].name; stored product fields written from request in modifyProductSubmit. Distinct from reflected searchTerm root.',
    },
}


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def fingerprint(finding):
    return finding['rule'], tuple(sorted(
        (r['file'], r['line'], r.get('column'), r.get('end_line'))
        for r in finding['locations']
    ))


def score_project(previous, coverage):
    project = previous['project']
    review = read(FINAL / project / 'full-review.json')
    scout = read(RUNS / '20261006-v2' / project / 'full-scout.json')
    static = read(RUNS / '20261006-v2' / 'static' / project / 'result.json')['rounds'][0]['findings']
    old_static = read(OLD / 'static' / project / 'result.json')['rounds'][0]['findings']
    old_by_id = {f['id']: fingerprint(f) for f in old_static}
    new_by_fp = {fingerprint(f): f['id'] for f in static}
    source_ids = {c['id'] for c in scout['candidates']}
    pool = review['stage']['result']['pool']['entries']
    candidates = {c['id']: c for c in review['candidates']}
    original_unreviewed = set(review['stage']['result']['unreviewed_candidate_ids'])
    unresolved = set(original_unreviewed)
    recovery_details = None
    if project == 'rv-dvna':
        recovery = read(OUTPUT / project / 'review-recovery.json')
        replacement = {c['related_target']: c for c in recovery['candidates'] if c['origin'] == 'ai'}
        original_pool = {p['source_candidate_id']: p for p in pool if p['origin'] == 'scout'}
        recovery_details = {'stage_id': recovery['stage_id'], 'usage': recovery['stage']['usage'],
                            'wall_seconds': recovery['wall_seconds'],
                            'unreviewed': len(recovery['stage']['result']['unreviewed_candidate_ids'])}
        for source, candidate in replacement.items():
            original_id = original_pool[source]['candidate_id']
            assert original_id in original_unreviewed
            if candidate['model_assessment'] != 'unknown':
                candidates[original_id] = {**candidate, 'original_candidate_id': original_id}
                unresolved.discard(original_id)
    matched = set()
    roots = []
    prefix = 'damn-vulnerable-flask-app-' if project == 'rv-flask' else 'dvna-'
    for prior in previous['roots']:
        suffix = prior['gold_id'].removeprefix(prefix)
        scout_ids = ASSOCIATIONS[project].get(suffix, '').split()
        assert set(scout_ids) <= source_ids, ('Unknown Scout ID', project, suffix)
        static_ids = [new_by_fp[old_by_id[i]] for i in prior['static_ids']
                      if old_by_id[i] in new_by_fp]
        if project == 'rv-dvna' and suffix == '016':
            static_ids += [f['id'] for f in static if f['rule'] == 'js/xss' and any(
                x['file'].endswith('/views/app/products.ejs') and x['line'] == 20
                for x in f['locations'])]
        entries = [p for p in pool if p.get('source_candidate_id') in scout_ids
                   or p.get('static_alert', {}).get('id') in static_ids]
        assessments = [{
            'review_candidate_id': p['candidate_id'],
            'source_candidate_id': p.get('source_candidate_id'),
            'static_id': p.get('static_alert', {}).get('id'),
            'assessment': candidates[p['candidate_id']]['model_assessment'],
            'latest_candidate_id': candidates[p['candidate_id']]['id'],
            'primary_location': candidates[p['candidate_id']]['location'],
        } for p in entries]
        matched.update(p['candidate_id'] for p in entries)
        roots.append({
            **{k: prior[k] for k in ('gold_id','gold_is_vulnerable','cwe','source_file','gold_location')},
            'scout_ids': scout_ids, 'static_ids': static_ids, 'review': assessments,
            'supported': any(a['assessment'] == 'supported' for a in assessments),
            'match_reason': REASONS[project].get(suffix, prior['match_reason']),
            'evaluation_status': 'provisional-source-condition-match-not-human-or-runtime-confirmed',
        })
    positive = [r for r in roots if r['gold_is_vulnerable']]
    supported = [r['gold_id'] for r in positive if r['supported']]
    static_roots = [r['gold_id'] for r in positive if r['static_ids']]
    unknown = [{
        'id': c['id'], 'title': c['title'], 'origin': c['origin'],
        'assessment': c['model_assessment'], 'location': c['location'],
    } for key,c in candidates.items() if key not in matched]
    return {
        'project': project, 'gold_positive_roots': len(positive),
        'gold_false_traps': sum(not r['gold_is_vulnerable'] for r in roots),
        'static_alerts': len(static), 'static_matched_roots': static_roots,
        'supported_positive_roots': supported,
        'additional_over_current_static': sorted(set(supported) - set(static_roots)),
        'missed_or_undecided_roots': [r['gold_id'] for r in positive if not r['supported']],
        'supported_false_traps': [r['gold_id'] for r in roots if not r['gold_is_vulnerable'] and r['supported']],
        'candidate_count': len(review['candidates']),
        'verdict_counts': dict(Counter(c['model_assessment'] for c in candidates.values())),
        'original_unreviewed': len(original_unreviewed),
        'unreviewed': len(unresolved),
        'bounded_review_recovery': recovery_details,
        'eligible_windows': coverage['eligible_windows'],
        'inspected_windows': coverage['combined_business_windows'],
        'task_status_counts': coverage['task_status_counts'],
        'scout_usage': scout['stage']['usage'], 'scout_seconds': scout['wall_seconds'],
        'review_usage': review['stage']['usage'], 'review_seconds': review['wall_seconds'],
        'roots': roots, 'unmapped_candidates': unknown,
    }


def main():
    assert read(FINAL / 'integrity.json')['input_and_implementation_unchanged']
    assert read(OUTPUT / 'integrity.json')['implementation_unchanged']
    old = read(OLD / 'discovery/root-adjudication.json')
    coverage = {r['project']: r for r in read(RUNS / '20261006-v3/summary.json')['projects']}
    projects = [score_project(p, coverage[p['project']]) for p in old['projects']]
    stages = {}
    per_run = []
    for run in sorted(RUNS.glob('20261006-v*')):
        new = []
        for path in sorted(run.glob('rv-*/*.json')):
            d = read(path)
            if 'stage' not in d or d['stage_id'] in stages:
                continue
            record = {'stage_id': d['stage_id'], 'first_run': run.name,
                      'project': path.parent.name, 'kind': d['stage']['kind'],
                      'prompt_version': d['stage']['prompt_version'],
                      'usage': d['stage']['usage'], 'wall_seconds': d['wall_seconds']}
            stages[d['stage_id']] = record
            new.append(record)
        per_run.append({'run_id': run.name, 'new_unique_stages': len(new),
                        **{key: sum(s['usage'].get(key, 0) for s in new)
                           for key in ('calls','input_tokens','output_tokens')}})
    report = {
        'run_id': OUTPUT.name, 'base_review_run': FINAL.name, 'date': '2026-10-06',
        'adjudication': 'agent-assisted evaluator, primary condition only; provisional, not human gold',
        'formal_benchmark': False, 'human_confirmed': False,
        'gui': False, 'target_services': False, 'exploit_execution': False,
        'ordinary_tests': 81,
        'limitations': [
            'Label-exposed development projects; not independent holdout or paper reproduction.',
            'Expanded input and much larger full-run budgets; gain cannot be attributed solely to new tasks or prompts.',
            'Supported is a source-condition model recommendation, not deployed exploit proof.',
            'Unmapped alarms remain unknown; no full precision/F1 computed.',
            'Inspected task records do not prove safe; task unknown and deferred assets retained.',
            'Inaccurate primary line positions and bundled secondary conditions still need correction.',
            'Full Scout uses its original frozen code; final review uses current frozen review7 code; stage receipts preserved.',
        ],
        'projects': projects,
        'total_supported_roots': sum(len(p['supported_positive_roots']) for p in projects),
        'total_gold_positive_roots': sum(p['gold_positive_roots'] for p in projects),
        'current_static_matched_roots': sum(len(p['static_matched_roots']) for p in projects),
        'old_supported_roots_primary_only': 16,
        'all_attempts_usage_by_run_deduplicated_by_stage_id': per_run,
        'all_attempt_stages': list(stages.values()),
    }
    save(OUTPUT / 'root-adjudication.json', report)
    public = {**report, 'projects': [{k:v for k,v in p.items() if k not in ('roots','unmapped_candidates')} for p in projects]}
    public.pop('all_attempt_stages')
    save(ROOT / 'benchmarks/experiments/discovery-coverage-summary.json', public)
    print(json.dumps(public, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
