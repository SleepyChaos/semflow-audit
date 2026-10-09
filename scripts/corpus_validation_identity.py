"""Bind official test receipts to complete inputs, fixed blobs and actual logs."""

import hashlib
from pathlib import Path

from app.services.context_materials import digest
from codeql_corpus_sources import ROOT, source_tree

SUFFIXES = {
    ".ql",
    ".qll",
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".vue",
    ".xsjs",
    ".raml",
    ".html",
    ".json",
    ".yml",
    ".yaml",
    ".xml",
    ".txt",
    ".expected",
}


def input_inventory(directory):
    return {
        p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.rglob("*")
        if p.is_file()
        and not any(part.startswith(".") for part in p.relative_to(directory).parts)
        and (p.suffix in SUFFIXES or p.name == "options")
    }


def verify_official_inputs(row):
    directory = ROOT / row["metadata"]["bundle"] / "tests"
    name = Path(row["query_path"]).name
    reference = next(
        r
        for r in row["metadata"]["official_development_tests"]
        if r["url"].endswith("/" + Path(name).stem + ".qlref")
    )
    language = row["language"]
    prefix = reference["url"].split("/" + language + "/", 1)[1].rsplit("/", 1)[0] + "/"
    tree = {r["path"]: r for r in source_tree(language)["tree"]}
    inventory = input_inventory(directory)
    for relative in inventory:
        original = tree.get(prefix + relative)
        if original and relative not in {
            name,
            "options",
            "qlpack.yml",
            "codeql-pack.lock.yml",
        }:
            blob = (directory / relative).read_bytes()
            git_hash = hashlib.sha1(
                b"blob " + str(len(blob)).encode() + b"\0" + blob
            ).hexdigest()
            if git_hash != original["sha"]:
                raise ValueError("Official fixture/oracle changed: " + relative)
    if inventory[name] != row["metadata"]["source_sha256"]:
        raise ValueError("Official query bytes changed")
    return digest(
        {
            "inputs": inventory,
            "dependencies": row["metadata"]["dependencies"],
            "commit": row["metadata"]["commit"],
        }
    ), max((directory / p).stat().st_mtime for p in inventory)
