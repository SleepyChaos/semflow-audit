"""Execute explicit immutable supplemental queries against the original scan DB."""

import json

from semflow_research.adapters.codeql.custom import prepare_query, run_query
from semflow_research.runtime.rule_inputs import read_rule


def apply(context, rules, directory, sarif_path):
    if not rules:
        return
    document = json.loads(sarif_path.read_bytes())
    for rule in rules:
        context.control.check_active(context.execution_id)
        query, modules, dependencies = read_rule(
            rule, context.artifacts, context.spec.language
        )
        pack = directory / "supplements" / str(rule.rule_id) / "pack"
        prepare_query(pack, context.spec.language, query, modules, dependencies)
        output = pack.parent / "results.sarif"
        run_query(
            directory / "database",
            pack,
            output,
            directory / "execution.log",
            context.spec.source.tree_sha256,
            _kernel=context,
        )
        extra = json.loads(output.read_bytes())
        for run in extra["runs"]:
            run.setdefault("properties", {})["audit_rule_version"] = str(rule.rule_id)
        document["runs"].extend(extra["runs"])
    (directory / "baseline.sarif").write_bytes(sarif_path.read_bytes())
    sarif_path.write_text(json.dumps(document))
