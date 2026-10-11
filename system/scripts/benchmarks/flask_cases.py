"""Evaluator-owned Flask API semantics; no fixtures enter model input or RAG."""

import hashlib
import json


def cases():
    prefix = "from flask import Flask, Blueprint, request, Response\nfrom markupsafe import escape\napp = Flask(__name__)\nbp = Blueprint('bp', __name__)\n"
    rows = []
    for owner in ("app", "bp"):
        for method in ("get", "post"):
            source = (
                prefix
                + f"@{owner}.{method}('/view')\ndef endpoint():\n    return request.args['payload'] # target\n"
            )
            if owner == "bp":
                source += "app.register_blueprint(bp)\n"
            rows.append((f"{owner}_{method}", True, source))
    rows.extend(
        [
            (
                "route_control",
                True,
                prefix
                + "@app.route('/view')\ndef endpoint():\n    return request.args['payload'] # target\n",
            ),
            (
                "routed_parameter",
                True,
                prefix
                + "@app.get('/<payload>')\ndef endpoint(payload):\n    return payload # target\n",
            ),
            (
                "escaped",
                False,
                prefix
                + "@app.get('/view')\ndef endpoint():\n    return escape(request.args['payload']) # target\n",
            ),
            (
                "constant",
                False,
                prefix
                + "@app.post('/view')\ndef endpoint():\n    return '<p>constant</p>' # target\n",
            ),
            (
                "plain_text",
                False,
                prefix
                + "@app.get('/view')\ndef endpoint():\n    return Response(request.args['payload'], mimetype='text/plain') # target\n",
            ),
            (
                "json_dict",
                False,
                prefix
                + "@app.get('/view')\ndef endpoint():\n    return {'value': request.args['payload']} # target\n",
            ),
            (
                "unrelated_receiver",
                False,
                prefix
                + "class Receiver:\n    def get(self, path):\n        return lambda fn: fn\nother = Receiver()\n@other.get('/view')\ndef endpoint():\n    return request.args['payload'] # target\n",
            ),
            (
                "unregistered_function",
                False,
                prefix + "def get():\n    return request.args['payload'] # target\n",
            ),
        ]
    )
    return [
        {
            "id": name,
            "file": name + ".py",
            "source": source,
            "line": next(
                i for i, line in enumerate(source.splitlines(), 1) if "# target" in line
            ),
            "vulnerable": vulnerable,
        }
        for name, vulnerable, source in rows
    ]


def dataset_hash(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def score(rows, findings):
    predictions = {
        (loc["file"], loc["line"]) for f in findings for loc in f["locations"]
    }
    decisions = []
    for row in rows:
        hit = (row["file"], row["line"]) in predictions
        decisions.append(
            {
                "id": row["id"],
                "predicted": hit,
                "vulnerable": row["vulnerable"],
                "classification": ("TP" if row["vulnerable"] else "FP")
                if hit
                else ("FN" if row["vulnerable"] else "TN"),
            }
        )
    counts = {
        key: sum(r["classification"] == key for r in decisions)
        for key in ("TP", "FP", "FN", "TN")
    }
    target_positions = {(r["file"], r["line"]) for r in rows}
    return {
        "decisions": decisions,
        "counts": counts,
        "precision": counts["TP"] / (counts["TP"] + counts["FP"])
        if counts["TP"] + counts["FP"]
        else None,
        "recall": counts["TP"] / (counts["TP"] + counts["FN"]),
        "extra_positions_unadjudicated": sorted(predictions - target_positions),
        "all_alert_count": len(findings),
    }
