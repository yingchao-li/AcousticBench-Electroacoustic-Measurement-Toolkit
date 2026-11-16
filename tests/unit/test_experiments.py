"""Unit tests for the experiment framework.

Covers the registry (exactly E01–E16, unique codes), the context/result
dataclasses, the runner's code resolution, artefact persistence and the small
shared analysis helpers used by the experiments.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from acousticbench.exceptions import ExperimentError
from acousticbench.experiments import (
    EXPERIMENTS,
    ExperimentContext,
    ExperimentResult,
    ExperimentRunner,
    ExperimentSpec,
)
from acousticbench.experiments import base as experiments_base
from acousticbench.experiments import common, synthetic_common
from acousticbench.synthetic import build_cases

matplotlib.use("Agg")


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------
def test_registry_contains_exactly_e01_to_e16():
    expected = tuple(f"E{i:02d}" for i in range(1, 17))
    assert tuple(sorted(EXPERIMENTS)) == expected
    assert len(EXPERIMENTS) == 16
    for code in expected:
        spec = EXPERIMENTS[code]
        assert isinstance(spec, ExperimentSpec)
        assert spec.code == code
        assert spec.title
        assert spec.description
        assert spec.module.startswith("acousticbench.experiments.e")
        assert callable(spec.runner)


def test_registry_modules_match_specs():
    from acousticbench.experiments.registry import MODULES

    assert len(MODULES) == 16
    assert tuple(spec.module for spec in EXPERIMENTS.values()) == MODULES


def test_registry_guards(monkeypatch):
    from acousticbench.experiments import registry

    # Duplicate experiment codes are rejected at build time.
    monkeypatch.setattr(registry, "_MODULES", (registry.MODULES[0], registry.MODULES[0]))
    with pytest.raises(RuntimeError, match="Duplicate experiment code"):
        registry._build_registry()

    # A module without the required metadata is rejected.
    fake = types.ModuleType("acousticbench.experiments.fake_experiment")
    fake.CODE = "E99"
    fake.TITLE = ""
    fake.run = lambda context: None
    monkeypatch.setitem(sys.modules, "acousticbench.experiments.fake_experiment", fake)
    monkeypatch.setattr(registry, "_MODULES", ("acousticbench.experiments.fake_experiment",))
    with pytest.raises(RuntimeError, match="must define CODE, TITLE and run"):
        registry._build_registry()


def test_experiment_spec_is_frozen():
    spec = EXPERIMENTS["E01"]
    with pytest.raises(Exception):
        spec.code = "X"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# context and result dataclasses
# ---------------------------------------------------------------------------
def test_experiment_context(config, small_dataset, bands):
    context = ExperimentContext(
        code="E02", dataset=small_dataset, config=config, seed=1234
    )
    assert context.code == "E02"
    assert context.dataset is small_dataset
    assert context.parameters == {}
    assert context.params() == config.experiment_params("E02")
    assert context.params("E07") == config.experiment_params("E07")
    provenance = context.data_provenance()
    assert provenance["dataset_path"] == small_dataset.path.name
    assert provenance["sha256"] == ""
    assert provenance["n_frequencies"] == 2049
    assert provenance["n_subjects"] == 14
    assert provenance["n_reinsertions"] == 3
    assert provenance["n_devices"] == 14
    assert provenance["invalid_policy"] == "exclude"
    assert context.bands() == bands
    # Deterministic RNG per context.
    first = context.rng.random(3)
    second = context.rng.random(3)
    np.testing.assert_array_equal(first, second)


def test_experiment_result_defaults_and_to_dict():
    result = ExperimentResult(code="E01", title="Demo")
    assert result.status == "completed"
    assert result.to_dict()["code"] == "E01"
    result.tables["table"] = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    result.figures["figure"] = plt.figure()
    result.metrics = {
        "numpy_int": np.int64(3),
        "numpy_float": np.float64(1.5),
        "nan_value": float("nan"),
        "bool": np.bool_(True),
        "array": np.arange(3),
        "path": Path("/tmp/example"),
        "nested": {"list": [np.int64(1)]},
    }
    result.duration_s = 1.23456
    payload = result.to_dict()
    assert payload["tables"]["table"] == {"rows": 2, "columns": ["a", "b"]}
    assert payload["figures"] == ["figure"]
    assert payload["metrics"]["numpy_int"] == 3
    assert payload["metrics"]["nan_value"] is None
    assert payload["duration_s"] == 1.235
    assert json.dumps(payload)  # serialisable
    plt.close(result.figures["figure"])
    result.figures = {}


# ---------------------------------------------------------------------------
# runner: discovery and error handling
# ---------------------------------------------------------------------------
def test_resolve_codes(config, tmp_path):
    runner = ExperimentRunner(config, output_root=tmp_path / "out")
    assert runner.resolve_codes(None) == list(config.experiments.enabled)
    assert runner.resolve_codes("E02") == ["E02"]
    assert runner.resolve_codes(["E02", "E09"]) == ["E02", "E09"]
    with pytest.raises(ExperimentError, match="Unknown experiment"):
        runner.resolve_codes(["E01", "E99"])
    assert runner.specs() == EXPERIMENTS


def test_run_unknown_code_raises(config, small_dataset, tmp_path):
    runner = ExperimentRunner(config, output_root=tmp_path / "out")
    with pytest.raises(ExperimentError, match="Unknown experiment"):
        runner.run("E99", dataset=small_dataset, save=False)


# ---------------------------------------------------------------------------
# artefact persistence
# ---------------------------------------------------------------------------
def _fabricated_result() -> ExperimentResult:
    figure, axis = plt.subplots()
    axis.plot([0, 1, 2], [0, 1, 4])
    return ExperimentResult(
        code="E01",
        title="Fabricated Experiment",
        status="completed",
        metrics={"n": np.int64(2), "nan": float("nan")},
        tables={
            "first table": pd.DataFrame({"x": [1, 2], "y": [3, 4]}),
            "second/table": pd.DataFrame({"z": [5.0]}),
        },
        figures={"demo figure": figure},
        narrative="Synthetic narrative.",
        warnings=["a warning"],
        parameters={"code": "E01"},
        data_provenance={"dataset": "synthetic"},
    )


def test_save_writes_all_artefacts(config, small_dataset, tmp_path):
    runner = ExperimentRunner(config, output_root=tmp_path / "out")
    result = _fabricated_result()
    spec = EXPERIMENTS["E01"]
    directory = runner.save(result, spec, small_dataset)
    assert directory.is_dir()
    assert (directory / "result.json").is_file()
    assert (directory / "summary.md").is_file()
    assert (directory / "config_snapshot.json").is_file()
    assert (directory / "tables" / "first_table.csv").is_file()
    assert (directory / "tables" / "second_table.csv").is_file()
    assert (directory / "figures" / f"demo_figure.{config.experiments.figure_format}").is_file()
    assert result.artifacts["tables"] == ["first_table.csv", "second_table.csv"]
    assert result.artifacts["figures"] == [f"demo_figure.{config.experiments.figure_format}"]
    assert result.figures == {}  # figures are closed after saving
    payload = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    assert payload["code"] == "E01"
    assert payload["metrics"]["n"] == 2
    assert payload["metrics"]["nan"] is None
    assert payload["tables"]["first table"]["rows"] == 2
    assert payload["status"] == "completed"
    assert payload["artifacts"] == {
        "tables": ["first_table.csv", "second_table.csv"],
        "figures": [f"demo_figure.{config.experiments.figure_format}"],
    }
    markdown = (directory / "summary.md").read_text(encoding="utf-8")
    assert "Fabricated Experiment" in markdown
    assert "Synthetic narrative." in markdown
    assert "a warning" in markdown
    assert "Data provenance" in markdown
    snapshot = json.loads((directory / "config_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["project_seed"] == config.project.seed
    assert snapshot["experiment_parameters"] == {"code": "E01"}
    table = pd.read_csv(directory / "tables" / "first_table.csv")
    assert list(table.columns) == ["x", "y"]


def test_save_cleans_stale_artefacts_and_compresses_large_tables(
    config, small_dataset, tmp_path
):
    runner = ExperimentRunner(config, output_root=tmp_path / "out")
    spec = EXPERIMENTS["E01"]
    directory = runner.save(_fabricated_result(), spec, small_dataset)
    stale_table = directory / "tables" / "stale.csv"
    stale_table.write_text("stale\n", encoding="utf-8")
    stale_figure = directory / "figures" / "stale.png"
    stale_figure.write_bytes(b"stale")

    big = ExperimentResult(
        code="E01",
        title="Fabricated Experiment",
        tables={"big": pd.DataFrame({"a": np.arange(2500, dtype=float)})},
    )
    directory_again = runner.save(big, spec, small_dataset)
    assert directory_again == directory
    assert not stale_table.exists()
    assert not stale_figure.exists()
    compressed = directory / "tables" / "big.csv.gz"
    assert compressed.is_file()
    reloaded = pd.read_csv(compressed)
    assert len(reloaded) == 2500
    assert reloaded["a"].iloc[-1] == 2499.0
    payload = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    assert payload["artifacts"]["tables"] == ["big.csv.gz"]
    assert payload["artifacts"]["figures"] == []
    # The gzip table is written with a fixed numeric format.
    assert compressed.stat().st_size > 0


def test_markdown_error_and_empty_sections(config, small_dataset, tmp_path):
    runner = ExperimentRunner(config, output_root=tmp_path / "out")
    result = ExperimentResult(
        code="E02",
        title="Broken",
        status="failed",
        error="ValueError: boom",
        duration_s=0.5,
    )
    markdown = runner.markdown(result)
    assert "**Status:** `failed`" in markdown
    assert "## Error" in markdown
    assert "ValueError: boom" in markdown
    assert "## Metrics" in markdown


def test_write_index(config, tmp_path):
    runner = ExperimentRunner(config, output_root=tmp_path / "out")
    first = ExperimentResult(code="E01", title="First", status="completed")
    first.artifacts = {"tables": ["a.csv"], "figures": ["a.png"]}
    first.duration_s = 0.1
    second = ExperimentResult(
        code="E02", title="Second", status="failed", error="boom"
    )
    second.duration_s = 0.2
    # Directories exist for the directory name recovery.
    (runner.output_root / "E01_first").mkdir(parents=True)
    (runner.output_root / "E02_second").mkdir(parents=True)
    index_path = runner.write_index([first, second])
    assert index_path.is_file()
    assert (runner.output_root / "experiment_index.csv").is_file()

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["project"] == config.project.name
    assert payload["version"] == config.project.version
    assert [entry["code"] for entry in payload["experiments"]] == ["E01", "E02"]
    assert payload["experiments"][1]["status"] == "failed"

    summary = pd.read_csv(runner.output_root / "experiment_index.csv")
    assert len(summary) == 2
    assert list(summary["code"]) == ["E01", "E02"]
    assert summary.loc[0, "n_tables"] == 1
    assert summary.loc[0, "n_figures"] == 1
    assert summary.loc[1, "error"] == "boom"
    assert summary.loc[0, "directory"] == "E01_first"
    assert summary.loc[1, "directory"] == "E02_second"

    # Writing a subset must preserve previously indexed experiments.
    runner.write_index([second])
    merged = json.loads(index_path.read_text(encoding="utf-8"))
    assert [entry["code"] for entry in merged["experiments"]] == ["E01", "E02"]
    merged_summary = pd.read_csv(runner.output_root / "experiment_index.csv")
    assert list(merged_summary["code"]) == ["E01", "E02"]


def test_write_index_tolerates_corrupt_previous_index(config, tmp_path):
    runner = ExperimentRunner(config, output_root=tmp_path / "out")
    index_path = runner.output_root / "experiment_index.json"
    index_path.write_text("{not valid json", encoding="utf-8")
    result = ExperimentResult(code="E01", title="First", status="completed")
    runner.write_index([result])
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert [entry["code"] for entry in payload["experiments"]] == ["E01"]


def test_directory_slug(config, tmp_path):
    runner = ExperimentRunner(config, output_root=tmp_path / "out")
    result = ExperimentResult(code="E03", title="A / B:C (Test)!", status="completed")
    assert runner._directory(result).name == "E03_a___b_c__test"


def test_experiment_table_frame(small_dataset):
    cube = small_dataset.reur()
    frame = experiments_base.experiment_table_frame(cube)
    assert "level_db" in frame.columns
    assert len(frame) == cube.values.size


# ---------------------------------------------------------------------------
# synthetic_common helpers
# ---------------------------------------------------------------------------
def test_build_suite_and_category_selection(config):
    small_config = config.with_overrides({"synthetic": {"n_cases": 40}})
    cases = synthetic_common.build_suite(small_config, persist_manifest=False)
    assert len(cases) == 40
    assert {case.category for case in cases} == {"gain", "snr", "thd", "frequency_response"}
    gain_cases = synthetic_common.category_cases(cases, "gain")
    assert len(gain_cases) == 10
    assert all(case.category == "gain" for case in gain_cases)
    with pytest.raises(ValueError, match="No synthetic cases"):
        synthetic_common.category_cases(cases, "banana")
    reference = synthetic_common.reference_cases(cases)
    assert 0 < len(reference) < len(cases)
    assert all(case.is_reference_condition for case in reference)


def test_build_suite_manifest(config, tmp_path):
    small_config = config.with_overrides(
        {"synthetic": {"n_cases": 8}, "paths": {"results_dir": str(tmp_path / "results")}}
    )
    cases = synthetic_common.build_suite(small_config, persist_manifest=True)
    manifest_dir = tmp_path / "results" / "synthetic"
    assert manifest_dir.is_dir()
    assert list(manifest_dir.iterdir())


def test_error_summary_semantics():
    empty = synthetic_common.error_summary([np.nan, np.nan], 0.1, unit="dB")
    assert empty["n"] == 0
    assert empty["median_abs_error"] is None
    assert empty["target_met"] is False
    assert empty["target"] == pytest.approx(0.1)
    assert empty["unit"] == "dB"

    within = synthetic_common.error_summary([-0.05, 0.02, 0.0, 0.1], 0.1, unit="dB")
    assert within["n"] == 4
    assert within["median_abs_error"] == pytest.approx(0.035)
    assert within["mean_abs_error"] == pytest.approx(0.0425)
    assert within["max_abs_error"] == pytest.approx(0.1)
    assert within["fraction_within_target"] == pytest.approx(1.0)
    assert within["target_met"] is True

    outside = synthetic_common.error_summary([0.05, 0.2, np.nan], 0.1, unit="dB")
    assert outside["n"] == 2
    assert outside["fraction_within_target"] == pytest.approx(0.5)
    assert outside["target_met"] is False

    assert synthetic_common.error_dataframe(
        [{"case_id": 2, "v": 1}, {"case_id": 1, "v": 2}]
    )["case_id"].tolist() == [1, 2]
    assert synthetic_common.error_dataframe([]).empty


# ---------------------------------------------------------------------------
# shared analysis helpers (experiments/common.py)
# ---------------------------------------------------------------------------
def test_nearest_frequency():
    frequencies = np.array([50.0, 100.0, 1000.0, 2000.0])
    assert common.nearest_frequency(frequencies, 990.0) == pytest.approx(1000.0)
    assert common.nearest_frequency(frequencies, 10.0) == pytest.approx(50.0)
    assert common.nearest_frequency(frequencies, 5000.0) == pytest.approx(2000.0)


def test_percentile_curves(small_dataset):
    cube = small_dataset.reur()
    frame = common.percentile_curves(cube, reference=20e-6, frequency_min=50.0, frequency_max=4000.0)
    assert {"frequency_hz", "median_db", "q10", "q90", "n_valid", "device", "family"}.issubset(
        frame.columns
    )
    assert frame["frequency_hz"].min() >= 50.0
    assert frame["frequency_hz"].max() <= 4000.0
    levels = cube.level_array(reference=20e-6)
    keep = (cube.freq_hz >= 50.0) & (cube.freq_hz <= 4000.0)
    row_index = 0
    expected = np.nanpercentile(levels[keep][row_index, 0].reshape(-1), 50)
    assert frame.loc[row_index, "median_db"] == pytest.approx(expected)


def test_band_summary_and_subject_helpers(small_dataset, bands):
    frame = small_dataset.reur().band_levels(bands, reference=20e-6)
    frame["family"] = "open_ear"
    frame["family_label"] = "Open Ear"
    summary = common.band_summary(frame, value_col="level_db")
    assert {"median_db", "mean_db", "sd_db", "n", "q25_db", "q75_db"}.issubset(summary.columns)
    assert (summary["median_db"] >= summary["q25_db"]).all()
    assert (summary["median_db"] <= summary["q75_db"]).all()

    means = common.subject_means(frame, value_col="level_db", group_cols=("family", "band"))
    assert "subject_mean" in means.columns
    assert means.groupby(["family", "band"]).size().max() == 14

    ci = common.mean_ci(frame, value_col="level_db", group_cols=("family", "band"))
    assert {"n", "mean_db", "sd_db", "se_db", "ci_low_db", "ci_high_db"}.issubset(ci.columns)
    assert (ci["ci_low_db"] <= ci["mean_db"]).all()
    assert (ci["ci_high_db"] >= ci["mean_db"]).all()
    assert (ci["n"] == 14).all()
    np.testing.assert_allclose(
        common.summarize_subjects(
            frame, value_col="level_db", group_cols=("family", "band")
        )["mean_db"].to_numpy(),
        ci["mean_db"].to_numpy(),
    )
    assert common.band_labels(bands)[0] == bands[0].label


def test_mean_ci_degenerate_cases():
    frame = pd.DataFrame(
        {
            "group": ["a", "a", "b", "c"],
            "subject": [1, 2, 1, 1],
            "value": [1.0, np.nan, 5.0, np.nan],
            "valid": [True, True, True, True],
        }
    )
    ci = common.mean_ci(frame, value_col="value", group_cols=("group",))
    assert set(ci["group"]) == {"a", "b", "c"}
    single = ci.loc[ci["group"] == "b"].iloc[0]
    assert np.isnan(single["sd_db"]) and np.isnan(single["se_db"])
    assert np.isnan(single["ci_low_db"])
    # A group whose only subject value is non-finite contributes n = 0.
    empty = ci.loc[ci["group"] == "c"].iloc[0]
    assert empty["n"] == 0
    assert np.isnan(empty["mean_db"]) and np.isnan(empty["ci_high_db"])


# ---------------------------------------------------------------------------
# real end-to-end runner (integration / slow)
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_data
def test_runner_run_e01_real_data(config, dataset, tmp_path):
    runner = ExperimentRunner(config, output_root=tmp_path / "experiments")
    result = runner.run("E01", dataset=dataset, save=True)
    assert result.status == "completed", result.error
    assert result.error is None
    assert result.duration_s > 0
    assert len(result.tables) >= 3
    assert result.parameters["code"] == "E01"
    assert result.data_provenance["n_subjects"] == 14
    assert "hha_median_db_spl_at_1000Hz" in result.metrics
    directory = runner._directory(result)
    assert (directory / "result.json").is_file()
    payload = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    # Figures are closed and recorded as artefact file names by the runner.
    assert payload["figures"] == []
    assert len(result.artifacts["figures"]) >= 3
    assert len(result.artifacts["tables"]) >= 3
