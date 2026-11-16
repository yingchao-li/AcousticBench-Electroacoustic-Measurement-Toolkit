"""End-to-end format tests for the PDF, Excel and HTML report builders."""

from __future__ import annotations

from pathlib import Path

import pytest

from acousticbench.config import load_config
from acousticbench.report import (
    build_all_reports,
    build_excel_report,
    build_html_report,
    build_pdf_report,
    load_saved_audit,
    load_saved_results,
)

_VALID_SHEET = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ _-.")


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def saved_results(config):
    results = load_saved_results(config.results_dir, config)
    if not results:
        pytest.skip("No persisted experiment results available for report tests")
    return results


@pytest.fixture(scope="module")
def saved_audit(config):
    return load_saved_audit(config.results_dir)


def test_build_all_reports_creates_three_formats(saved_results, saved_audit, config, tmp_path):
    paths = build_all_reports(
        saved_results,
        tmp_path,
        config=config,
        audit=saved_audit,
        formats=("pdf", "excel", "html"),
    )
    assert set(paths) == {"pdf", "excel", "html"}
    for fmt, path in paths.items():
        assert path.is_file(), f"{fmt} report missing"
        assert path.stat().st_size > 0, f"{fmt} report is empty"
        assert path.parent == tmp_path
        assert path.name.startswith("AcousticBench_Report_")
    # One timestamp shared by all formats.
    assert len({path.stem for path in paths.values()}) == 1


def test_pdf_starts_with_pdf_magic(saved_results, saved_audit, config, tmp_path):
    path = build_pdf_report(
        saved_results, tmp_path / "report.pdf", config=config, audit=saved_audit
    )
    assert path.is_file() and path.stat().st_size > 0
    assert path.read_bytes()[:5] == b"%PDF-"
    assert sorted(saved_results, key=lambda item: item.code)[0].code in path.read_bytes().decode(
        "latin-1", errors="ignore"
    )


def test_html_is_self_contained_and_mentions_required_sections(
    saved_results, saved_audit, config, tmp_path
):
    path = build_html_report(
        saved_results, tmp_path / "report.html", config=config, audit=saved_audit
    )
    document = path.read_text(encoding="utf-8")
    assert document.startswith("<!DOCTYPE html>")
    assert "<style>" in document and "data:image/png;base64," in document
    assert "Limitations" in document
    assert "MATLAB is not available in this environment" in document
    for result in saved_results:
        assert result.title in document
        assert result.code in document
    if saved_audit is not None:
        assert "Data quality audit" in document


def test_excel_sheet_names_valid(saved_results, saved_audit, config, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = build_excel_report(
        saved_results, tmp_path / "report.xlsx", config=config, audit=saved_audit
    )
    assert path.is_file() and path.stat().st_size > 0
    workbook = openpyxl.load_workbook(path, read_only=True)
    try:
        names = workbook.sheetnames
        assert "Summary" in names
        assert "Data Audit" in names
        assert "Statistics" in names
        assert len({name.casefold() for name in names}) == len(names)
        for name in names:
            assert 0 < len(name) <= 31, f"invalid sheet name length: {name!r}"
            assert not any(character not in _VALID_SHEET for character in name), name
    finally:
        workbook.close()


def test_build_all_reports_rejects_empty_results(config, tmp_path):
    from acousticbench.exceptions import ReportError

    with pytest.raises(ReportError):
        build_all_reports([], tmp_path, config=config)


def test_build_all_reports_rejects_unknown_format(saved_results, config, tmp_path):
    from acousticbench.exceptions import ReportError

    with pytest.raises(ReportError):
        build_all_reports(saved_results, tmp_path, config=config, formats=("docx",))


def test_excel_caps_large_tables_and_skips_empty_ones(config, tmp_path):
    """Large tables are capped at 500 rows with an on-disk path note; empty sheets are skipped."""
    import numpy as np
    import openpyxl
    import pandas as pd

    from acousticbench.experiments.base import ExperimentResult

    large = pd.DataFrame(
        {
            "frequency_hz": np.linspace(100.0, 10000.0, 1200),
            "level_db": np.linspace(-10.0, 10.0, 1200),
        }
    )
    result = ExperimentResult(
        code="E99",
        title="Synthetic Cap Test",
        status="completed",
        metrics={"n_rows": 1200},
        tables={"large_curve": large, "empty_table": pd.DataFrame()},
    )
    path = build_excel_report([result], tmp_path / "capped.xlsx", config=config, audit=None)
    workbook = openpyxl.load_workbook(path, read_only=True)
    try:
        names = workbook.sheetnames
        assert "E99 large_curve" in names
        assert not any("empty_table" in name for name in names)
        worksheet = workbook["E99 large_curve"]
        assert worksheet.max_row <= 510
        note = worksheet.cell(row=4, column=1).value
        assert note and "first 500 of 1200 rows" in note
        assert "tables/large_curve.csv" in note
        assert workbook["Statistics"].max_row >= 2
        assert workbook["Summary"].max_row >= 7
    finally:
        workbook.close()
