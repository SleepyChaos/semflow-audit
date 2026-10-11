"""Import pinned official Python API references and compiler-checked XSS examples."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT.name != "semflow-audit-ui":
    raise SystemExit("Run this importer only from the independent semflow-audit-ui copy.")
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]

import yaml
from codeql_corpus_sources import COMMITS, library_topics, source_tree
from app.adapters.codeql.custom import fixed_dependencies, search_paths
from app.adapters.codeql.process import run_command
from app.adapters.retrieval.knowledge import import_knowledge
from app.core.audit_config import audit_settings

def main():
    refs = library_topics("python")
    print(f"Imported pinned references: {len(refs)}", flush=True)
    deps = fixed_dependencies("python")
    pack = audit_settings.CODEQL_PACK_PATH / "codeql/python-queries/1.6.0"
    tree = {entry["path"]: entry for entry in source_tree("python")["tree"]}
    records = []
    for path in sorted((pack / "Security/CWE-079").glob("*.ql")):
        blob = path.read_bytes()
        relative = path.relative_to(pack).as_posix()
        git_hash = hashlib.sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest()
        if git_hash != tree["ql/src/" + relative]["sha"]:
            raise ValueError("Installed query differs from the pinned official source")
        unit = ROOT / "artifacts/materials/ui-xss" / path.stem
        unit.mkdir(parents=True, exist_ok=True)
        (unit / "generated.ql").write_bytes(blob)
        (unit / "qlpack.yml").write_text(yaml.safe_dump({
            "name": "audit/official-xss-example", "version": "0.0.1",
            "dependencies": {"codeql/python-all": deps["codeql/python-all"]["version"]},
        }))
        (unit / "codeql-pack.lock.yml").write_text(yaml.safe_dump({"lockVersion": "1.0.0", "dependencies": deps}))
        print(f"Compiler check: {path.name}", flush=True)
        run_command([
            audit_settings.CODEQL_BIN, "query", "compile", "--check-only",
            "--additional-packs=" + search_paths(unit), "--ram=2048",
            str(unit / "generated.ql"),
        ], unit / "compile.log", 600)
        metadata = {
            "api_version": deps["codeql/python-all"]["version"],
            "query_pack": audit_settings.PYTHON_QUERY_PACK, "dependencies": deps,
            "cwe": "CWE-079", "trust": "pinned_codeql_source", "license": "MIT",
            "commit": COMMITS["python"],
            "source_url": f'https://github.com/github/codeql/blob/{COMMITS["python"]}/python/ql/src/{relative}',
            "source_sha256": hashlib.sha256(blob).hexdigest(),
            "original_path": str((unit / "generated.ql").relative_to(ROOT)),
            "validation": {"status": "passed", "kind": "compile_only",
                           "meaning": "Actual compiler check only; no independent test execution"},
        }
        record = import_knowledge(
            None, "python official " + path.stem,
            "pinned-codeql-query:" + audit_settings.PYTHON_QUERY_PACK + "/" + relative,
            "python", blob.decode(), metadata, corpus="rule_example",
        )
        records.append(record)
        print(f"Imported example: {path.name}", flush=True)
    summary = ROOT / "artifacts/materials/ui-xss/import-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps({"references": refs, "examples": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(refs)} references and {len(records)} real compiler-checked examples.")

if __name__ == "__main__":
    main()
