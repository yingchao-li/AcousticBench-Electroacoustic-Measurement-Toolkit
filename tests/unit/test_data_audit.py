"""Unit tests for the data-quality audit (:mod:`acousticbench.data.audit`).

The audit is inherently a real-data artefact (it verifies the documented
physical signatures of ``Data.mat``), so these tests are marked
``requires_data``.  The report/serialisation helpers are additionally checked
against the real audit result.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from acousticbench.data.audit import AuditFinding, DataAudit, DataAuditor

pytestmark = pytest.mark.requires_data


@pytest.fixture(scope="module")
def audit(dataset):
    """Session-scoped audit of the real dataset (shared by this module)."""
    return dataset.audit()


def test_audit_findings_and_statuses(audit):
    assert isinstance(audit, DataAudit)
    assert audit.n_errors == 0
    assert audit.n_warnings == 0
    assert audit.passed is True
    assert len(audit.findings) == 17
    for finding in audit.findings:
        assert finding.severity in {"info", "warning", "error"}
        assert finding.status in {"INFO", "PASS", "WARN"}
        row = finding.to_row()
        assert set(row) == {"status", "severity", "code", "message", "expected", "observed"}


def test_audit_finding_status_logic():
    passed = AuditFinding(severity="info", code="x", message="ok", passed=True)
    assert passed.status == "PASS"
    failed = AuditFinding(severity="warning", code="y", message="bad", passed=False)
    assert failed.status == "WARN"
    info = AuditFinding(severity="warning", code="z", message="caveat", passed=None)
    assert info.status == "INFO"


def test_audit_frames(audit):
    assert isinstance(audit.variables, pd.DataFrame)
    assert len(audit.variables) == 7
    assert set(audit.variables["key"]) == {
        "M_ha2edM",
        "M_ha2edR",
        "M_ha2haf",
        "M_ls2edM",
        "M_ls2edR",
        "M_thr_ha",
        "M_REUR",
    }
    assert isinstance(audit.session_validity, pd.DataFrame)
    assert len(audit.session_validity) == 7
    assert isinstance(audit.invalid_sessions, pd.DataFrame)
    assert len(audit.invalid_sessions) == 18 * 5 + 19
    assert isinstance(audit.structural_validity, pd.DataFrame)
    assert len(audit.structural_validity) == 7
    checks = audit.checks_frame()
    assert len(checks) == 17
    assert set(checks["status"]) <= {"PASS", "WARN", "INFO"}


def test_audit_derived_sections(audit):
    derived = audit.derived
    assert "unit_interpretation" in derived
    assert "probe_tube_presence_effect" in derived
    assert "structural_signatures" in derived
    assert "repeatability" in derived
    assert derived["unit_interpretation"]["hha_median_db_spl_500_4000Hz"] == pytest.approx(
        derived["unit_interpretation"]["hha_median_db_spl_500_4000Hz"]
    )
    signs = derived["probe_tube_presence_effect"]
    assert signs["delta_hha_100Hz_median_db"] < 0
    assert signs["delta_reoig_2kHz_median_db"] > 0
    assert signs["delta_threshold_125Hz_median_db"] < 0
    # The documented in-situ free-field scaling caveat must be visible.
    codes = {finding.code for finding in audit.findings}
    assert "absolute_free_field_scaling" in codes


def test_audit_axes_metadata(audit):
    assert audit.frequency_axis["n_bins"] == 2049
    assert audit.frequency_axis["min_hz"] == 0.0
    assert audit.frequency_axis["max_hz"] == pytest.approx(22050.0)
    assert audit.frequency_axis["resolution_hz"] == pytest.approx(22050.0 / 2048.0)
    assert audit.frequency_axis["uniform"] is True
    assert audit.threshold_axis["frequencies_hz"] == [125, 250, 500, 750, 1000, 2000]
    assert audit.threshold_axis["quantisation_db"] == pytest.approx(1.0)
    assert audit.threshold_axis["max_quantisation_residual_db"] <= 1e-6


def test_audit_to_dict_is_json_serialisable(audit):
    payload = audit.to_dict()
    text = json.dumps(payload)
    reloaded = json.loads(text)
    assert reloaded["summary"]["n_errors"] == 0
    assert reloaded["summary"]["n_checks"] == 17
    assert reloaded["provenance"]["licence"] == "CC BY 4.0"
    assert len(reloaded["checks"]) == 17
    assert len(reloaded["variables"]) == 7


def test_audit_markdown(audit):
    text = audit.to_markdown()
    assert "AcousticBench data audit" in text
    assert "0 warnings" in text
    assert "0 errors" in text
    assert "Structural validity rules" in text
    assert "M_ha2edM" in text
    assert "10.5281/zenodo.20023285" in text


def test_audit_save_artefacts(audit, tmp_path):
    paths = audit.save(tmp_path)
    assert set(paths) == {
        "json",
        "markdown",
        "variables",
        "session_validity",
        "invalid_sessions",
        "structural_validity",
        "checks",
        "figure",
    }
    for path in paths.values():
        assert path.is_file()
        assert path.stat().st_size > 0
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["summary"]["n_errors"] == 0
    figure_bytes = paths["figure"].read_bytes()
    assert figure_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    listed = sorted(path.name for path in tmp_path.iterdir())
    for expected in (
        "data_audit.json",
        "data_audit.md",
        "variables.csv",
        "session_validity.csv",
        "invalid_sessions.csv",
        "structural_validity.csv",
        "checks.csv",
        "data_audit_overview.png",
    ):
        assert expected in listed


def test_audit_save_without_figure(audit, tmp_path):
    paths = audit.save(tmp_path, make_figure=False)
    assert "figure" not in paths
    assert not (tmp_path / "data_audit_overview.png").exists()
    assert not (tmp_path / "figure_error.txt").exists()


def test_data_auditor_uses_dataset_config(dataset):
    auditor = DataAuditor(dataset, config=dataset.config)
    assert auditor.config is dataset.config
    # A fresh auditor instance starts without findings.
    assert auditor.findings == []
    assert auditor.derived == {}
