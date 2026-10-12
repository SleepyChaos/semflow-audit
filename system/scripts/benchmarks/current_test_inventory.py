"""Reconcile existing public catalogs and references; never execute target code."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks"
DATE = "2026-10-08"


def load(path):
    return json.loads((ROOT / path).read_text())


def canonical(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())


def main():
    datasets, papers = [], {}
    additions = load("benchmarks/manifests/current-inventory-additions.json")
    catalogs = {
        name: load(f"benchmarks/catalog/{name}.json")
        for name in ("discovery", "rules", "repair")
    }

    def add_paper(title, year, source, url=None, paths=(), note=None):
        key = canonical(title)
        row = papers.setdefault(
            key,
            {
                "title": title,
                "citation_year": year,
                "sources": [],
                "urls": [],
                "local_paths": [],
                "notes": [],
            },
        )
        row["sources"].append(source)
        if year and (row["citation_year"] is None or year > row["citation_year"]):
            row["citation_year"] = year
        if url and url not in row["urls"]:
            row["urls"].append(url)
        for path in paths:
            if path not in row["local_paths"]:
                row["local_paths"].append(path)
        if note:
            row["notes"].append(note)
        return row

    for direction, catalog in catalogs.items():
        for d in catalog["datasets"]:
            datasets.append(
                {
                    **d,
                    "direction": direction,
                    "source_registry": f"benchmarks/catalog/{direction}.json",
                }
            )
        for p in catalog["papers"]:
            add_paper(
                p["title"],
                p["year"],
                f"catalog/{direction}",
                p["official_url"],
                ["benchmarks/" + s for s in p.get("local_paths", [])],
                p.get("publication_status"),
            )
    for name in ("references.bib", "rule-generation-references.bib"):
        for block in re.split(r"(?m)^@", (ROOT / "research/catalog" / name).read_text())[
            1:
        ]:
            title = re.search(r"(?<![a-zA-Z])title\s*=\{([^\n]+?)\}(?:,|\s*$)", block)
            year = re.search(r"(?<![a-zA-Z])year\s*=\{(\d{4})\}", block)
            url = re.search(r"(?<![a-zA-Z])url\s*=\{([^}]+)\}", block)
            if title:
                add_paper(
                    title.group(1),
                    int(year.group(1)) if year else None,
                    f"research/catalog/{name}",
                    url.group(1) if url else None,
                )
    for p in load("research/catalog/rule-generation-paper-manifest.json")["papers"]:
        add_paper(
            p["title"],
            p["year"],
            "rule-generation-paper-manifest",
            p.get("url"),
            note=f"Recorded reading scope: {p.get('read_scope', 'not specified')}",
        )

    extra = additions["extra"]
    for title, year, url, source in extra:
        add_paper(title, year, source, url)
    freshness_path = BENCH / "manifests/freshness-and-coverage-review.json"
    if freshness_path.exists():
        freshness = json.loads(freshness_path.read_text())
        for metadata in freshness["arxiv_metadata"] + freshness["formal_metadata"]:
            row = papers.get(canonical(metadata["title"]))
            if row is None:
                continue
            row["date_verification"] = "primary_metadata_rechecked_2026-10-08"
            for key in (
                "first_public_date",
                "last_arxiv_revision_date",
                "formal_publication_year",
                "formal_publication_date",
                "formal_publication_month",
                "venue",
            ):
                if key in metadata:
                    row[key] = metadata[key]
            if metadata.get("source") and metadata["source"] not in row["urls"]:
                row["urls"].insert(0, metadata["source"])
    for p in load("research/catalog/papers-manifest.json"):
        match = re.search(r"(\d{4}\.\d{4,5})", p["url"])
        if not match:
            continue
        for row in papers.values():
            if any(match.group(1) in url for url in row["urls"]):
                path = "artifacts/papers/" + p["file"]
                if path not in row["local_paths"]:
                    row["local_paths"].append(path)
                break

    datasets += additions["datasets"]
    common = additions["common"]
    executed = additions["executed"]
    for d in datasets:
        d["primary_program"] = (
            "common-benchmarks" if d["id"] in common else "specialized-comparisons"
        )
        d["current_execution"] = executed.get(
            d["id"], "no matched formal result admitted in this inventory"
        )
        d["local_presence"] = [
            {
                "path": p,
                "exists": (BENCH / p).exists(),
                "nonempty": (BENCH / p).stat().st_size > 0
                if (BENCH / p).is_file()
                else None,
            }
            for p in d.get("local_paths", [])
        ]
    all_pdf = sorted(
        p
        for folder in (BENCH / "papers", ROOT / "research/papers", ROOT / "artifacts/papers")
        for p in folder.rglob("*.pdf")
        if p.is_file()
    )
    for row in papers.values():
        row["local_pdf_files"] = [
            p
            for p in row["local_paths"]
            if p.endswith(".pdf")
            and (ROOT / p).is_file()
            and (ROOT / p).read_bytes()[:5] == b"%PDF-"
        ]
        row["local_html_files"] = [
            p
            for p in row["local_paths"]
            if p.endswith(".html") and (ROOT / p).is_file()
        ]
        row["availability"] = (
            "local_pdf"
            if row["local_pdf_files"]
            else "local_html"
            if row["local_html_files"]
            else "registered_reference_only"
        )
    tool_rows = additions["tool_rows"]
    methods = additions["methods"]
    report = {
        "as_of": DATE,
        "scope": "Catalogs + existing bibliography/method manifests + recent competitor sources; no new paid tests or source execution",
        "counting": "Material entries are not independent runnable datasets; publications dedup by normalized title, versions merged; reading/download/replication distinct",
        "summary": {
            "material_entries": len(datasets),
            "material_by_direction": dict(Counter(d["direction"] for d in datasets)),
            "primary_program_counts": dict(
                Counter(d["primary_program"] for d in datasets)
            ),
            "unique_literature_entries": len(papers),
            "citation_years": dict(
                Counter(str(p["citation_year"]) for p in papers.values())
            ),
            "local_pdf_files": len(all_pdf),
            "local_pdf_publications": sum(
                bool(p["local_pdf_files"]) for p in papers.values()
            ),
            "local_html_publications_without_pdf": sum(
                p["availability"] == "local_html" for p in papers.values()
            ),
            "reference_only_publications": sum(
                p["availability"] == "registered_reference_only"
                for p in papers.values()
            ),
            "main_external_comparators": len(tool_rows),
            "main_comparators_actually_run": 3,
            "additional_method_candidates": len(methods),
        },
        "datasets": datasets,
        "papers": list(papers.values()),
        "comparators": [
            {"id": i, "name": n, "status": s, "program": g, "limits": l, "url": u}
            for i, n, s, g, l, u in tool_rows
        ],
        "additional_method_candidates": methods,
        "pdf_files": [
            {
                "path": str(p.relative_to(ROOT)),
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in all_pdf
        ],
    }
    (BENCH / "manifests/current-test-inventory.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    lines = [
        "# 当前文献登记（去重）",
        "",
        f"更新：{DATE}。按标题合并预印本/会议版；不是已通读或已复现数量。",
        "",
        "年份按登记的正式发表/引用年；QLCoder首稿2025、正式2026；IRIS首稿2024、正式2025；Vul-RAG首稿2024、登记正式2026。两项历史基准文献不作为2025–2026主要方法引用。",
        "",
        "首次公开/修订日期和正式发表记录按一手元数据补充；空白表示本次未核准，不把arXiv DOI当正式发表证明。完整核查见[时效与对照覆盖报告](../test-programs/freshness-and-coverage-review.md)。",
        "",
        "| # | 文献 | 引用年 | 首次公开 / 最新arXiv版 | 正式发表记录 | 本地状态 |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for i, row in enumerate(papers.values(), 1):
        title = f"[{row['title']}]({row['urls'][0]})" if row["urls"] else row["title"]
        status = {
            "local_pdf": "PDF已核对文件头",
            "local_html": "HTML原文已存",
            "registered_reference_only": "链接/书目/阅读记录；未核对本地全文",
        }[row["availability"]]
        dates = (
            f"{row.get('first_public_date', '—')} / "
            f"{row.get('last_arxiv_revision_date', '—')}"
        )
        venue = row.get("venue", "本次未核准正式发表")
        lines.append(
            f"| {i} | {title} | {row['citation_year']} | {dates} | {venue} | {status} |"
        )
    (BENCH / "catalog/current-papers.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
