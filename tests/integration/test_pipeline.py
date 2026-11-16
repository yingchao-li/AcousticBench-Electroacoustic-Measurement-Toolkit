"""End-to-end integration tests spanning several AcousticBench layers.

These tests deliberately exercise the *composition* of the modules on the real
measurement dataset: data loading → measurement quantities → band aggregation →
subject-level statistics → paired inference.  They are marked ``integration``,
``slow`` and ``requires_data`` so they can be excluded from the fast CI subset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from acousticbench.data import load_dataset
from acousticbench.exceptions import DataValidationError
from acousticbench.measurements.ptpe import ptpe_hha_band_levels, ptpe_reoig_band_levels
from acousticbench.measurements.transfer import hha_band_levels
from acousticbench.stats.bootstrap import bootstrap_paired_ci
from acousticbench.stats.descriptive import describe_array, subject_means
from acousticbench.stats.effect_size import cohen_dz, hedges_g, rank_biserial
from acousticbench.stats.paired import (
    normality_check,
    paired_summary,
    paired_t_test,
    wilcoxon_signed_rank,
)
from acousticbench.types import Condition, Probe

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.requires_data]


def _subject_level_band_levels(dataset, bands, condition) -> pd.DataFrame:
    """Subject-level 125 Hz band levels for the closed earmold family."""
    frame = hha_band_levels(dataset, bands, probe=Probe.REFERENCE, condition=condition)
    frame = frame.loc[frame["valid"]].copy()
    frame = frame.loc[
        (frame["family"] == "closed_earmold") & (frame["band_center_hz"] == 125.0)
    ]
    return subject_means(
        frame, value_col="level_db", subject_col="subject", group_cols=("family", "band")
    )


def _paired_samples(dataset, bands) -> tuple[np.ndarray, np.ndarray]:
    measurement = _subject_level_band_levels(dataset, bands, Condition.MEASUREMENT)
    reference = _subject_level_band_levels(dataset, bands, Condition.REFERENCE)
    assert len(measurement) == len(reference) == 14
    merged = measurement.merge(
        reference, on=["family", "band", "subject"], suffixes=("_meas", "_ref")
    )
    assert len(merged) == 14
    return (
        merged["level_db_meas"].to_numpy(dtype=float),
        merged["level_db_ref"].to_numpy(dtype=float),
    )


def test_dataset_to_paired_statistics_pipeline(dataset, config, bands):
    measured, reference = _paired_samples(dataset, bands)
    differences = measured - reference
    assert np.all(np.isfinite(differences))
    # Inserting the measurement probe reduces the low-frequency driver level.
    assert np.mean(differences) < 0

    result = paired_t_test(measured, reference)
    assert result.n == 14
    assert result.method == "paired_t_test"
    assert result.mean_diff < 0
    assert 0.0 <= result.p_value <= 1.0
    assert result.ci_high < 0
    assert np.isfinite(result.t) and np.isfinite(result.df)
    assert result.effect_size_name == "cohen_dz"
    assert result.effect_size < 0

    effect = cohen_dz(differences)
    assert np.isfinite(effect) and effect < 0
    assert np.isfinite(hedges_g(differences))
    assert np.isfinite(rank_biserial(differences))
    normality = normality_check(differences)
    assert "p_value" in normality or "p" in normality

    wilcoxon = wilcoxon_signed_rank(measured, reference)
    assert wilcoxon["n"] == 14
    assert 0.0 <= wilcoxon["p_value"] <= 1.0

    summary = paired_summary(
        measured,
        reference,
        bootstrap={"n_resamples": 500, "confidence": 0.95, "seed": config.project.seed},
    )
    for key in (
        "method",
        "n",
        "mean_diff",
        "p_value",
        "wilcoxon",
        "effect_size",
        "bootstrap_ci_low",
        "bootstrap_ci_high",
        "bootstrap_n",
    ):
        assert key in summary, key
    assert summary["bootstrap_ci_low"] <= summary["bootstrap_ci_high"]
    assert summary["bootstrap_n"] == 14


def test_bootstrap_paired_ci_pipeline(dataset, config, bands):
    measured, reference = _paired_samples(dataset, bands)
    boot = bootstrap_paired_ci(
        measured, reference, n_resamples=500, confidence=0.95, seed=config.project.seed
    )
    assert boot.n == 14
    assert boot.estimate == pytest.approx(float(np.mean(measured - reference)))
    assert boot.ci_low <= boot.ci_high
    assert boot.ci_high < 0
    assert boot.confidence == pytest.approx(0.95)
    assert boot.method == "percentile"


def test_band_level_and_ptpe_pipeline(dataset, bands):
    ptpe = ptpe_hha_band_levels(dataset, bands)
    ptpe = ptpe.loc[ptpe["valid"]]
    summary = (
        ptpe.groupby(["family", "band_center_hz"], as_index=False)["ptpe_db"]
        .agg(["median", "mean", "count"])
        .reset_index()
    )
    assert len(summary) == 4 * len(bands)
    low = summary.loc[summary["band_center_hz"] == 63.0]
    # The low-frequency probe-tube presence effect is negative for most
    # earmold families; the median across families is clearly negative.
    assert float(low["median"].median()) < -3.0
    assert int((low["median"] < 0).sum()) >= 3
    assert (low["count"] > 0).all()

    reoig = ptpe_reoig_band_levels(dataset, bands)
    reoig = reoig.loc[reoig["valid"]]
    mid = reoig.loc[reoig["band_center_hz"] == 1000.0]
    medians = mid.groupby("family")["ptpe_db"].median()
    assert medians["closed_earmold"] > 0
    assert medians["nugget_earmold"] > 0


def test_describe_array_on_real_subjects(dataset, bands):
    measured, _ = _paired_samples(dataset, bands)
    description = describe_array(measured)
    assert description["n"] == 14
    assert description["mean"] == pytest.approx(float(np.mean(measured)))
    assert np.isfinite(description["sd"]) and description["sd"] > 0
    assert description["ci_low"] < description["mean"] < description["ci_high"]


def test_load_dataset_missing_path_raises(config, tmp_path):
    with pytest.raises(DataValidationError):
        load_dataset(tmp_path / "missing.mat", config=config)
