"""Evaluator-only provisional source-condition matching; never used as model input."""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "artifacts/research/discovery-semantics/20261007-v3"
CLOSURE = ROOT / "artifacts/research/discovery-semantics/20261007-v4"
PRIOR = (
    ROOT / "artifacts/research/discovery-coverage/20261006-v6/root-adjudication.json"
)


def read(path):
    return json.loads(path.read_text())


def extra_matches(project, h):
    prop = h.get("security_property")
    loc = h["primary_location"]
    file = loc["file"]
    line = loc["line"]
    endpoint = h.get("endpoint", "")
    if project == "rv-flask":
        if not file.endswith("/app.py"):
            return []
        # Distinct security property and primary endpoint; bundled secondary claims get no credit.
        if prop == "authentication":
            bounds = {
                "/evaluate": ("012", 111, 130),
                "/lookup": ("013", 132, 150),
                "/xml": ("014", 152, 181),
                "/sayhi": ("015", 185, 205),
            }
            if endpoint in bounds:
                suffix, start, end = bounds[endpoint]
                return [suffix] if start <= line <= end else []
        selectors = [
            ("001", "input_injection", 111, 130),
            ("002", "output_encoding", 111, 130),
            ("005", "input_injection", 152, 181),
            ("006", "output_encoding", 152, 181),
            ("007", "input_injection", 185, 205),
            ("008", "output_encoding", 185, 205),
            ("009", "secrets_config", 15, 15),
            ("011", "secrets_config", 208, 208),
        ]
        return [
            suffix
            for suffix, p, start, end in selectors
            if prop == p and start <= line <= end
        ]
    if (
        prop == "security_logging"
        and file.endswith("/core/passport.js")
        and 20 <= line <= 48
    ):
        return ["009"]
    if prop == "rate_limiting" and (
        (file.endswith("/routes/main.js") and 51 <= line <= 55)
        or (
            file.endswith("/core/passport.js")
            and 20 <= line <= 48
            and endpoint in {"/login", "POST /login"}
        )
    ):
        return ["012"]
    if (
        prop == "state_integrity"
        and file.endswith("/routes/main.js")
        and 40 <= line <= 43
    ):
        return ["011"]
    if prop == "authorization" and (
        (file.endswith("/routes/app.js") and 41 <= line <= 44)
        or (file.endswith("/core/appHandler.js") and 203 <= line <= 211)
    ):
        return ["010"]
    if (
        prop == "object_ownership"
        and file.endswith("/core/appHandler.js")
        and 145 <= line <= 175
    ):
        return ["003"]
    selectors = [
        ("001", "input_injection", "/core/appHandler.js", 6, 19),
        ("002", "input_injection", "/core/appHandler.js", 27, 46),
        ("004", "other", "/core/appHandler.js", 185, 190),
        ("005", "input_injection", "/core/appHandler.js", 213, 224),
        ("006", "input_injection", "/core/appHandler.js", 229, 243),
        ("007", "authentication", "/core/authHandler.js", 20, 39),
        ("008", "state_integrity", "/core/authHandler.js", 45, 86),
        ("013", "secrets_config", "/server.js", 24, 24),
        ("014", "secrets_config", "/server.js", 27, 27),
        ("015", "output_encoding", "/views/app/adminusers.ejs", 40, 42),
        ("016", "output_encoding", "/views/app/products.ejs", 20, 20),
        ("017", "output_encoding", "/views/app/products.ejs", 50, 50),
    ]
    return [
        suffix
        for suffix, p, endfile, start, end in selectors
        if prop == p and file.endswith(endfile) and start <= line <= end
    ]


def score_project(prior, closure=False):
    project = prior["project"]
    path = RUN / project / "combined-review.json"
    if not path.exists():
        return None
    current = read(path)
    result = current["stage"]["result"]
    candidates = {c["id"]: c for c in current["candidates"]}
    roots = {
        r["gold_id"]: {**r, "review": [], "supported": False} for r in prior["roots"]
    }
    prefix = "damn-vulnerable-flask-app-" if project == "rv-flask" else "dvna-"
    new = read(RUN / project / "source-scout.json")
    metadata = {
        h["candidate_id"]: h
        for u in new["stage"]["result"]["units"]
        for h in u.get("hypotheses", [])
    }
    entries = list(result["pool"]["entries"])
    remaining = set(result.get("unreviewed_candidate_ids", []))
    closure_data = None
    for closure_root in ([CLOSURE, ROOT / "artifacts/research/discovery-semantics/20261007-v5", ROOT / "artifacts/research/discovery-semantics/20261007-v6", ROOT / "artifacts/research/discovery-semantics/20261007-v7"] if "--final" in sys.argv else [CLOSURE]) if closure else []:
        if not (closure_root / project / "review-closure.json").exists():
            continue
        closure_data=read(closure_root/project/"review-closure.json")
        replacements={c["identity_key"]:c for c in closure_data["candidates"]}
        seen_keys={c["identity_key"] for c in candidates.values()}
        for identifier,candidate in list(candidates.items()):
            replacement=replacements.get(candidate["identity_key"])
            if identifier in remaining and replacement and replacement["model_assessment"] not in {"unknown","pending"}:
                candidates[identifier]={**replacement,"original_review_candidate_id":identifier}
                remaining.discard(identifier)
        for entry in closure_data["stage"]["result"]["pool"]["entries"]:
            candidate=next(c for c in closure_data["candidates"] if c["id"]==entry["candidate_id"])
            if candidate["identity_key"] not in seen_keys:
                entries.append(entry);candidates[candidate["id"]]=candidate
                seen_keys.add(candidate["identity_key"])
                if candidate["model_assessment"] in {"unknown","pending"}: remaining.add(candidate["id"])
        path=closure_root/project/"targeted-scout.json"
        if path.exists():
            targeted=read(path)
            metadata.update({h["candidate_id"]:h for u in targeted["stage"]["result"]["units"] for h in u.get("hypotheses",[])})
    mapped = set()
    for entry in entries:
        candidate = candidates[entry["candidate_id"]]
        source = entry.get("source_candidate_id")
        static = entry.get("static_alert", {}).get("id")
        matches = [
            key
            for key, r in roots.items()
            if source in r["scout_ids"] or static in r["static_ids"]
        ]
        if source in metadata:
            matches += [prefix + s for s in extra_matches(project, metadata[source])]
        for key in set(matches):
            root = roots[key]
            mapped.add(candidate["id"])
            root["review"].append(
                {
                    "candidate_id": candidate["id"],
                    "source_id": source,
                    "origin": entry["origin"],
                    "assessment": candidate["model_assessment"],
                    "primary_location": candidate["location"],
                    "title": candidate["title"],
                    "weakness": candidate["weakness"],
                }
            )
            root["supported"] |= candidate["model_assessment"] == "supported"
    positives = [r for r in roots.values() if r["gold_is_vulnerable"]]
    supported = [r["gold_id"] for r in positives if r["supported"]]
    return {
        "project": project,
        "supported_roots": supported,
        "missed_or_undecided": [r["gold_id"] for r in positives if not r["supported"]],
        "false_traps_supported": [
            r["gold_id"]
            for r in roots.values()
            if not r["gold_is_vulnerable"] and r["supported"]
        ],
        "candidate_count": len(candidates),
        "unreviewed": len(remaining),
        "closure_usage": closure_data["stage"]["usage"] if closure_data else None,
        "closure_seconds": closure_data["wall_seconds"] if closure_data else None,
        "verdict_counts": dict(
            Counter(c["model_assessment"] for c in candidates.values())
        ),
        "new_scout_coverage": new["stage"]["result"]["coverage"],
        "scout_usage": new["stage"]["usage"],
        "review_usage": current["stage"]["usage"],
        "scout_seconds": new["wall_seconds"],
        "review_seconds": current["wall_seconds"],
        "roots": list(roots.values()),
        "unmapped": [
            {
                "id": c["id"],
                "title": c["title"],
                "assessment": c["model_assessment"],
                "location": c["location"],
            }
            for c in candidates.values()
            if c["id"] not in mapped
        ],
    }


def main():
    closure = "--closure" in sys.argv or "--final" in sys.argv
    output = ROOT / "artifacts/research/discovery-semantics/20261007-v7" if "--final" in sys.argv else CLOSURE if closure else RUN
    projects = [
        q for p in read(PRIOR)["projects"] if (q := score_project(p, closure=closure)) is not None
    ]
    report = {
        "run_id": output.name,
        "base_run": RUN.name,
        "adjudication": "provisional evaluator source-condition associations; not human or runtime confirmed",
        "labels_used_for_adjudication_only": True,
        "formal_benchmark": False,
        "gold_positive_roots": 31,
        "supported_roots": sum(len(p["supported_roots"]) for p in projects),
        "projects": projects,
        "limitations": [
            "Development projects already exposed to evaluator; no independent generalization claim.",
            "Bundled secondary conditions not granted roots; unmapped alarms are not adjudicated FP.",
            "Flask004 and013 describe executable rp but rp has no source binding; keep upstream labels unchanged and flag disagreement.",
            "New source inspection and larger review budgets; not a single-factor or equal-cost improvement claim.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "root-adjudication.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(
        json.dumps(
            {
                **{k: v for k, v in report.items() if k != "projects"},
                "projects": [
                    {
                        k: v
                        for k, v in p.items()
                        if k
                        in {
                            "project",
                            "supported_roots",
                            "missed_or_undecided",
                            "candidate_count",
                            "unreviewed",
                            "false_traps_supported",
                        }
                    }
                    for p in projects
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
