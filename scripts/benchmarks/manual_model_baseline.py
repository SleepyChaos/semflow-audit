"""Hand-configured sink oracle: template upper bound, not automatic no-AI extraction."""

import argparse
import json
from pathlib import Path

from app.adapters.codeql.custom import fixed_dependencies, prepare_query
from app.adapters.codeql.rule_spec import detector_template
from scripts.benchmarks.framework_ablation import fixture
from scripts.benchmarks.rule_ablation_oracles import evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    results = []
    for index in range(3):
        data, _ = fixture(index)
        member = ["evaluate", "run_code", "execute"][index]
        module = f'''import python
import semmle.python.ApiGraphs
import semmle.python.security.dataflow.CodeInjectionCustomizations
class ManualSink extends CodeInjection::Sink {{
  ManualSink() {{ this = API::moduleImport("auditbridge{index}").getMember("{member}").getACall().getArg({index}) }}
}}
'''
        query, provenance = detector_template("python", "eval")
        query = query.replace(
            "import python\n", "import python\nimport FrameworkModel\n", 1
        )
        pack = output / "manual-model-baseline" / data["id"]
        prepare_query(
            pack,
            "python",
            query,
            {"FrameworkModel.qll": module},
            fixed_dependencies("python"),
        )
        result = evaluate(output / "holdouts" / data["id"], pack, data, pack / "oracle")
        results.append(
            {
                "case": data["id"],
                "result": result,
                "meaning": "Human-specified golden sink mapping; template upper bound, not automatic discovery",
            }
        )
        (output / "manual-model-baseline.json").write_text(
            json.dumps(results, indent=2)
        )
        print(data["id"], result["status"], flush=True)


if __name__ == "__main__":
    main()
