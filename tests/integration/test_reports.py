"""Integration tests for the report builders.

The builders are consumed through their public API only (the report modules
are owned by the dashboard layer).  Saved E01/E02 artefacts are checked into
``results/experiments`` so this test is data-free and runs in CI.
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.integration


def _saved_e01_e02(repo_root, config):
    report = pytest.importorskip(
        "acousticbench.report", reason="report layer is not available"
    )
    results_root = repo_root / "results" / "experiments"
    if not results_root.is_dir():
        pytest.skip(f"No saved experiment results under {results_root}")
    results = [
        result for result in report.load_saved_results(results_root, config)
        if result.code in {"E01", "E02"}
    ]
    if {result.code for result in results} != {"E01", "E02"}:
        pytest.skip("Saved E01/E02 results are not available")
    return report, results


def test_build_pdf_excel_html_from_saved_e01_e02(repo_root, config, tmp_path):
    report, results = _saved_e01_e02(repo_root, config)
    audit = report.load_saved_audit(repo_root / "results")
    output_dir = tmp_path / "reports"
    paths = report.build_all_reports(
        results,
        output_dir,
        config=config,
        audit=audit,
        formats=("pdf", "excel", "html"),
    )
    assert set(paths) == {"pdf", "excel", "html"}
    for path in paths.values():
        assert path.is_file()
        assert path.stat().st_size > 0
        assert path.parent == output_dir

    # PDF: readable, at least a cover + contents + experiment pages.
    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(str(paths["pdf"]))
    assert len(reader.pages) >= 3
    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "AcousticBench" in pdf_text
    assert "E01" in pdf_text

    # Excel: summary sheet plus the experiment sheets from the configuration.
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.load_workbook(paths["excel"], read_only=True)
    assert "Summary" in workbook.sheetnames
    assert len(workbook.sheetnames) >= 2
    workbook.close()

    # HTML: self-contained page mentioning both experiments.
    html = paths["html"].read_text(encoding="utf-8")
    assert "<html" in html.lower()
    assert "AcousticBench" in html
    assert "E01" in html and "E02" in html


def test_report_metadata(repo_root, config, tmp_path):
    report, results = _saved_e01_e02(repo_root, config)
    paths = report.build_all_reports(
        results, tmp_path / "reports", config=config, formats=("html",)
    )
    metadata = report.report_metadata(paths)
    assert isinstance(metadata, dict)
    assert json.dumps(metadata)
    assert "html" in paths["html"].name.lower() or paths["html"].suffix == ".html"


def test_saved_results_carry_tables_and_figures(repo_root, config):
    report, results = _saved_e01_e02(repo_root, config)
    for result in results:
        assert result.status == "completed"
        assert result.directory is not None
        assert result.table_paths  # CSVs reloaded into frames
        assert result.figure_paths
        assert result.tables
        for path in result.table_paths.values():
            assert path.is_file()
        assert result.figure_items()
