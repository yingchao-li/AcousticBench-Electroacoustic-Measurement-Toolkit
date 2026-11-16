"""Bootstrap determinism and sanity tests (subject-level resampling)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from acousticbench.stats.bootstrap import (
    BootstrapResult,
    bootstrap_ci,
    bootstrap_paired_ci,
    cluster_bootstrap_ci,
)

SAMPLE = np.array([1.0, 2.0, 2.5, 3.0, 4.0, 5.5, 6.0, 7.0, 8.5, 9.0])


class TestBootstrapCi:
    def test_same_seed_same_interval(self) -> None:
        first = bootstrap_ci(SAMPLE, n_resamples=500, seed=1234)
        second = bootstrap_ci(SAMPLE, n_resamples=500, seed=1234)
        assert first.to_dict() == second.to_dict()
        assert first.seed == 1234
        assert first.method == "percentile"
        assert first.n_resamples == 500

    def test_different_seeds_generally_change_the_interval(self) -> None:
        sample = np.linspace(0.0, 20.0, 31)
        intervals = {
            (bootstrap_ci(sample, n_resamples=1000, seed=seed).ci_low,
             bootstrap_ci(sample, n_resamples=1000, seed=seed).ci_high)
            for seed in (1, 2, 3)
        }
        assert len(intervals) > 1

    def test_estimate_is_observed_statistic(self) -> None:
        result = bootstrap_ci(SAMPLE, n_resamples=200, seed=0)
        assert result.estimate == pytest.approx(float(np.mean(SAMPLE)))

    def test_interval_contains_estimate(self) -> None:
        result = bootstrap_ci(SAMPLE, n_resamples=2000, seed=20260422)
        assert result.ci_low <= result.estimate <= result.ci_high
        assert result.n == SAMPLE.size

    def test_higher_confidence_is_wider(self) -> None:
        low = bootstrap_ci(SAMPLE, n_resamples=1000, confidence=0.90, seed=7)
        high = bootstrap_ci(SAMPLE, n_resamples=1000, confidence=0.99, seed=7)
        assert (high.ci_high - high.ci_low) >= (low.ci_high - low.ci_low)

    def test_nan_entries_dropped_and_counted(self) -> None:
        result = bootstrap_ci([1.0, 2.0, np.nan, 3.0, np.inf], n_resamples=200, seed=3)
        assert result.n == 3
        assert result.estimate == pytest.approx(2.0)

    def test_median_statistic(self) -> None:
        result = bootstrap_ci(SAMPLE, statistic=np.median, n_resamples=500, seed=11)
        assert result.estimate == pytest.approx(float(np.median(SAMPLE)))
        assert result.ci_low <= result.estimate <= result.ci_high

    def test_bca_is_deterministic_and_contains_estimate(self) -> None:
        first = bootstrap_ci(SAMPLE, n_resamples=1000, seed=99, method="bca")
        second = bootstrap_ci(SAMPLE, n_resamples=1000, seed=99, method="bca")
        assert first.to_dict() == second.to_dict()
        assert first.method == "bca"
        assert first.ci_low <= first.estimate <= first.ci_high

    def test_invalid_settings_raise(self) -> None:
        with pytest.raises(ValueError):
            bootstrap_ci(SAMPLE, n_resamples=0)
        with pytest.raises(ValueError):
            bootstrap_ci(SAMPLE, confidence=1.0)
        with pytest.raises(ValueError):
            bootstrap_ci(SAMPLE, method="jackknife")
        with pytest.raises(ValueError):
            bootstrap_ci([1.0])
        with pytest.raises(ValueError):
            bootstrap_ci([np.nan, np.nan])

    def test_result_string_and_to_dict(self) -> None:
        result = bootstrap_ci(SAMPLE, n_resamples=100, seed=5)
        assert isinstance(result, BootstrapResult)
        text = str(result)
        assert "bootstrap" in text
        assert "95%" in text
        payload = result.to_dict()
        assert set(payload) == {
            "estimate",
            "ci_low",
            "ci_high",
            "confidence",
            "n_resamples",
            "method",
            "seed",
            "n",
        }


class TestBootstrapPairedCi:
    def test_estimate_is_mean_paired_difference(self) -> None:
        a = np.array([1.0, 2.0, 4.0, 6.0, 8.0])
        b = np.array([0.5, 2.5, 3.0, 5.0, 7.0])
        result = bootstrap_paired_ci(a, b, n_resamples=500, seed=3)
        assert result.estimate == pytest.approx(float(np.mean(a - b)))
        assert result.ci_low <= result.estimate <= result.ci_high

    def test_deterministic_given_seed(self) -> None:
        a = np.array([1.0, 2.0, 4.0, 6.0, 8.0])
        b = np.array([0.5, 2.5, 3.0, 5.0, 7.0])
        first = bootstrap_paired_ci(a, b, n_resamples=300, seed=42)
        second = bootstrap_paired_ci(a, b, n_resamples=300, seed=42)
        assert first.to_dict() == second.to_dict()

    def test_nan_pairs_dropped(self) -> None:
        a = np.array([1.0, np.nan, 3.0, 4.0, 5.0])
        b = np.array([0.0, 2.0, np.nan, 3.0, 4.0])
        result = bootstrap_paired_ci(a, b, n_resamples=200, seed=1)
        assert result.n == 3  # pairs (0, 0), (3, 3), (4, 4) are complete
        assert result.estimate == pytest.approx(float(np.mean([1.0, 1.0, 1.0])))

    def test_unequal_length_raises(self) -> None:
        with pytest.raises(ValueError):
            bootstrap_paired_ci([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_too_few_pairs_raises(self) -> None:
        with pytest.raises(ValueError):
            bootstrap_paired_ci([1.0, np.nan], [0.0, 1.0])


class TestClusterBootstrap:
    def _frame(self) -> pd.DataFrame:
        rng = np.random.default_rng(2026)
        rows = []
        for subject in range(1, 7):
            for repeat in range(2):
                rows.append(
                    {
                        "subject": subject,
                        "reinsertion": repeat,
                        "device": "A",
                        "level": 10.0 + subject + rng.normal(0.0, 0.1),
                    }
                )
        return pd.DataFrame(rows)

    def test_single_group(self) -> None:
        frame = self._frame()
        result = cluster_bootstrap_ci(
            frame, unit_col="subject", value_col="level", n_resamples=400, seed=8
        )
        assert isinstance(result, BootstrapResult)
        assert result.n == 6
        assert result.estimate == pytest.approx(frame["level"].mean())
        assert result.ci_low <= result.estimate <= result.ci_high

    def test_deterministic(self) -> None:
        frame = self._frame()
        first = cluster_bootstrap_ci(
            frame, unit_col="subject", value_col="level", n_resamples=200, seed=9
        )
        second = cluster_bootstrap_ci(
            frame, unit_col="subject", value_col="level", n_resamples=200, seed=9
        )
        assert first.to_dict() == second.to_dict()

    def test_grouped_returns_dataframe(self) -> None:
        frame = self._frame()
        frame.loc[frame.index[:4], "device"] = "B"
        result = cluster_bootstrap_ci(
            frame,
            unit_col="subject",
            value_col="level",
            group_cols=["device"],
            n_resamples=200,
            seed=10,
        )
        assert isinstance(result, pd.DataFrame)
        assert set(result["device"]) == {"A", "B"}
        assert {"estimate", "ci_low", "ci_high", "n"}.issubset(result.columns)
        assert (result["ci_low"] <= result["estimate"]).all()
        assert (result["estimate"] <= result["ci_high"]).all()

    def test_missing_columns_raise(self) -> None:
        frame = self._frame()
        with pytest.raises(ValueError):
            cluster_bootstrap_ci(frame, unit_col="nope", value_col="level")
        with pytest.raises(ValueError):
            cluster_bootstrap_ci(frame, unit_col="subject", value_col="nope")
