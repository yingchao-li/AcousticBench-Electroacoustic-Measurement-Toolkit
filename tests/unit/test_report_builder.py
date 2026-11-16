"""Tests for persisted-artefact loading in the report builder."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from acousticbench.config import load_config
from acousticbench.report.builder import (
    SavedExperimentResult,
    load_saved_audit,
    load_saved_results,
)


@pytest.fixture(scope="module")
def config():
    return load_config()


def _has_experiment(config, code: str) -> bool:
    root = config.results_dir / "experiments"
    return any(path.is_dir() and path.name.startswith(code) for path in root.glob("*"))


def test_load_saved_results_round_trip(config):
    """Persisted E01/E02 results load with tables and figure paths."""
    if not (_has_experiment(config, "E01") or _has_experiment(config, "E02")):
        pytest.skip("No persisted experiments in results/experiments (fixture absent)")

    results = load_saved_results(config.results_dir, config)
    assert results, "expected at least one saved experiment"
    assert all(isinstance(item, SavedExperimentResult) for item in results)
    codes = {item.code for item in results}
    assert {"E01", "E02"} & codes

    for item in results:
        assert item.title and item.code
        assert isinstance(item.metrics, dict)
        assert isinstance(item.tables, dict)
        assert isinstance(item.figure_paths, dict)
        assert item.directory is not None and item.directory.is_dir()
        for frame in item.tables.values():
            assert len(frame) >= 0
        for path in item.figure_paths.values():
            assert Path(path).is_file()


def test_load_saved_results_missing_root(tmp_path):
    """A missing results directory yields an empty list instead of an exception."""
    assert load_saved_results(tmp_path / "does_not_exist") == []

    empty_root = tmp_path / "results"
    (empty_root / "experiments").mkdir(parents=True)
    assert load_saved_results(empty_root) == []


def test_load_saved_audit(config):
    """The persisted audit is reconstructed with its checks and tables."""
    json_path = config.results_dir / "audit" / "data_audit.json"
    if not json_path.is_file():
        pytest.skip("No persisted data audit (results/audit/data_audit.json)")

    audit = load_saved_audit(config.results_dir)
    assert audit is not None
    assert audit.findings, "audit should contain automated checks"
    assert audit.dataset_summary, "audit should contain the dataset summary"
    assert audit.n_errors == 0
    assert not audit.checks_frame().empty
    assert not audit.session_validity.empty
    assert not audit.structural_validity.empty


def test_load_saved_audit_missing(tmp_path):
    assert load_saved_audit(tmp_path) is None


def test_load_saved_results_prefers_gzip_tables(tmp_path):
    """Compressed ``.csv.gz`` tables are preferred over stale ``.csv`` files."""
    import json

    experiment = tmp_path / "experiments" / "E99_dummy_experiment"
    tables = experiment / "tables"
    tables.mkdir(parents=True)
    (experiment / "result.json").write_text(
        json.dumps({"code": "E99", "title": "Dummy Experiment", "status": "completed"}),
        encoding="utf-8",
    )
    stale = pd.DataFrame({"frequency_hz": [100.0], "level_db": [-1.0]})
    current = pd.DataFrame(
        {"frequency_hz": [100.0, 200.0, 300.0], "level_db": [-1.0, -2.0, -3.0]}
    )
    stale.to_csv(tables / "curves.csv", index=False)
    current.to_csv(tables / "curves.csv.gz", index=False, compression="gzip")
    # A small table persisted only as plain CSV must still load.
    pd.DataFrame({"band": ["1 kHz"], "value_db": [2.0]}).to_csv(
        tables / "summary.csv", index=False
    )

    results = load_saved_results(tmp_path)
    assert len(results) == 1
    result = results[0]
    assert set(result.table_paths) == {"curves", "summary"}
    assert result.table_paths["curves"].name == "curves.csv.gz"
    assert len(result.tables["curves"]) == 3
    assert len(result.tables["summary"]) == 1
