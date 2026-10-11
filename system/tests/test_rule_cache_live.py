"""Actual regression for different candidates sharing audit/generated pack identity."""

import os

import pytest
from app.adapters.codeql.custom import fixed_dependencies, prepare_query, run_query
from app.adapters.codeql.scanner import CodeQLScanner
from app.domain.audit import ScanPlan


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("AUDIT_RUN_REAL_TOOLS") != "1", reason="requires actual CodeQL"
)
def test_dynamic_queries_do_not_reuse_previous_bqrs(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "sample.py").write_text('eval(input())\nint("3")\n')
    database = tmp_path / "database"
    CodeQLScanner().create_database(
        source, database, tmp_path / "create.log", ScanPlan("python", "", "")
    )
    header = """/** @id audit/cache-regression
 * @name cache regression
 * @description Dynamic query candidates must be reevaluated
 * @kind problem
 * @problem.severity warning
 * @precision low
 */
import python
"""
    outcomes = []
    for name in ("eval", "int"):
        pack = tmp_path / name
        query = (
            header
            + f'from Call c where c.getFunc().(Name).getId() = "{name}" select c, "{name}"\n'
        )
        prepare_query(pack, "python", query, {}, fixed_dependencies("python"))
        findings = run_query(
            database,
            pack,
            tmp_path / (name + ".sarif"),
            tmp_path / "execute.log",
            "cache-regression",
        )
        outcomes.append(
            {location["line"] for row in findings for location in row["locations"]}
        )
    assert outcomes == [{1}, {2}]
