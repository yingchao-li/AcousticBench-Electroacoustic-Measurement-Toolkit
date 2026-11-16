"""Integration tests for the experiment runner (subset) and synthetic suite."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from acousticbench.dsp.metrics import estimate_gain_db, estimate_snr_db, estimate_thd
from acousticbench.experiments import ExperimentRunner
from acousticbench.synthetic import build_cases, render_case

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# synthetic validation suite smoke (data-free)
# ---------------------------------------------------------------------------
def test_synthetic_suite_smoke(config):
    """Reference-condition synthetic cases must meet their documented targets."""
    cases = build_cases(
        n_cases=40, seed=config.project.seed, fs_hz=config.synthetic.fs_hz
    )
    assert len(cases) == 40
    reference = [case for case in cases if case.is_reference_condition]
    assert reference

    targets = config.synthetic.targets
    gain_error = None
    snr_error = None
    thd_error = None
    for case in reference:
        data = render_case(case)
        truth = data.ground_truth
        if case.category == "gain" and gain_error is None:
            estimate = estimate_gain_db(
                data.input, data.output, data.fs_hz, tone_hz=float(truth["tone_hz"])
            ).gain_db
            gain_error = abs(estimate - float(truth["gain_db"]))
        elif case.category == "snr" and snr_error is None:
            estimate = estimate_snr_db(
                data.output, data.fs_hz, float(truth["tone_hz"]), method="residual"
            ).snr_db
            snr_error = abs(estimate - float(truth["snr_db"]))
        elif case.category == "thd" and thd_error is None:
            estimate = estimate_thd(
                data.output,
                data.fs_hz,
                float(truth["tone_hz"]),
                n_harmonics=int(truth["n_harmonics"]),
            ).thd_percent
            thd_error = abs(estimate - float(truth["thd_percent"]))
    assert gain_error is not None and gain_error <= targets["gain_error_db"]
    assert snr_error is not None and snr_error <= targets["snr_error_db"]
    assert (
        thd_error is not None
        and thd_error <= targets["thd_error_percentage_points"]
    )
    assert all(np.isfinite([gain_error, snr_error, thd_error]))


# ---------------------------------------------------------------------------
# real experiment subset
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.requires_data
def test_experiment_subset_e02_e09(config, dataset, tmp_path):
    runner = ExperimentRunner(config, output_root=tmp_path / "experiments")
    results = runner.run_all(["E02", "E09"], dataset=dataset)
    assert [result.code for result in results] == ["E02", "E09"]
    by_code = {result.code: result for result in results}
    for code in ("E02", "E09"):
        result = by_code[code]
        assert result.status == "completed", (code, result.error)
        assert result.error is None
        directory = runner._directory(result)
        assert (directory / "result.json").is_file()
        assert (directory / "summary.md").is_file()
        payload = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        assert payload["status"] == "completed"
        assert payload["tables"]
        assert result.artifacts["figures"]
        assert result.duration_s > 0

    assert "report_frequencies_hz" in by_code["E02"].parameters
    e09_metrics = by_code["E09"].metrics
    assert e09_metrics["n_cases"] == 250
    assert e09_metrics["target_db"] == pytest.approx(0.1)
    assert e09_metrics["reference_summary"]["n"] > 0
    assert e09_metrics["target_met_in_reference_condition"] is True

    index_csv = tmp_path / "experiments" / "experiment_index.csv"
    assert index_csv.is_file()
    index = pd.read_csv(index_csv)
    assert list(index["code"]) == ["E02", "E09"]
    assert (index["status"] == "completed").all()
    index_json = json.loads(
        (tmp_path / "experiments" / "experiment_index.json").read_text(encoding="utf-8")
    )
    assert [entry["code"] for entry in index_json["experiments"]] == ["E02", "E09"]
