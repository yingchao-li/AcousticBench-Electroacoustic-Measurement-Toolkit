"""Paired t-test / Wilcoxon tests validated against scipy and closed forms."""

from __future__ import annotations

import numpy as np
import pytest
import scipy.stats as st

from acousticbench.stats.paired import (
    PairedTestResult,
    normality_check,
    paired_summary,
    paired_t_test,
    wilcoxon_signed_rank,
)

DATASETS = [
    (
        np.array([1.0, 2.0, 4.0, 7.0, 8.0, 10.0]),
        np.array([0.5, 2.5, 3.0, 6.0, 8.5, 9.0]),
    ),
    (
        np.array([10.0, 12.5, 9.0, 15.0, 11.0, 13.0, 8.5]),
        np.array([9.0, 11.0, 8.5, 13.0, 10.5, 12.0, 8.0]),
    ),
    (
        np.array([3.0, 5.0, 5.5, 9.0, 2.0, 7.5]),
        np.array([2.0, 6.0, 4.5, 7.0, 2.5, 6.0]),
    ),
]


class TestPairedTTest:
    @pytest.mark.parametrize(("a", "b"), DATASETS)
    def test_matches_scipy_ttest_rel(self, a: np.ndarray, b: np.ndarray) -> None:
        result = paired_t_test(a, b)
        reference = st.ttest_rel(a, b)
        assert isinstance(result, PairedTestResult)
        assert result.method == "paired_t_test"
        assert result.n == a.size
        assert result.df == a.size - 1
        assert result.t == pytest.approx(float(reference.statistic), rel=1e-12)
        assert result.p_value == pytest.approx(float(reference.pvalue), rel=1e-12)
        assert result.mean_a == pytest.approx(float(np.mean(a)))
        assert result.mean_b == pytest.approx(float(np.mean(b)))
        assert result.mean_diff == pytest.approx(float(np.mean(a - b)))
        assert result.sd_diff == pytest.approx(float(np.std(a - b, ddof=1)))
        assert result.effect_size_name == "cohen_dz"
        expected_dz = float(np.mean(a - b) / np.std(a - b, ddof=1))
        assert result.effect_size == pytest.approx(expected_dz, rel=1e-12)

    @pytest.mark.parametrize(("a", "b"), DATASETS)
    def test_ci_matches_closed_form(self, a: np.ndarray, b: np.ndarray) -> None:
        result = paired_t_test(a, b, confidence=0.95)
        differences = a - b
        se = np.std(differences, ddof=1) / np.sqrt(differences.size)
        quantile = st.t.ppf(0.975, differences.size - 1)
        assert result.ci_low == pytest.approx(float(np.mean(differences) - quantile * se))
        assert result.ci_high == pytest.approx(float(np.mean(differences) + quantile * se))

    def test_nan_pairs_excluded(self) -> None:
        a = np.array([1.0, np.nan, 4.0, 4.0, np.inf, 6.0])
        b = np.array([0.0, 2.0, 2.0, np.nan, 4.0, 5.0])
        result = paired_t_test(a, b)
        complete_a = np.array([1.0, 4.0, 6.0])
        complete_b = np.array([0.0, 2.0, 5.0])
        reference = st.ttest_rel(complete_a, complete_b)
        assert result.n == 3
        assert result.t == pytest.approx(float(reference.statistic))
        assert result.p_value == pytest.approx(float(reference.pvalue))
        assert result.mean_a == pytest.approx(float(np.mean(complete_a)))
        assert result.mean_b == pytest.approx(float(np.mean(complete_b)))

    def test_one_sided_alternatives_match_scipy(self) -> None:
        a, b = DATASETS[0]
        greater = paired_t_test(a, b, alternative="greater")
        reference = st.ttest_rel(a, b, alternative="greater")
        assert greater.p_value == pytest.approx(float(reference.pvalue))
        assert greater.ci_high == float("inf")
        less = paired_t_test(a, b, alternative="less")
        reference_less = st.ttest_rel(a, b, alternative="less")
        assert less.p_value == pytest.approx(float(reference_less.pvalue))
        assert less.ci_low == float("-inf")

    def test_to_dict_contains_all_fields(self) -> None:
        result = paired_t_test(*DATASETS[0]).to_dict()
        assert set(result) == {
            "method",
            "n",
            "mean_a",
            "mean_b",
            "mean_diff",
            "sd_diff",
            "t",
            "df",
            "p_value",
            "ci_low",
            "ci_high",
            "effect_size",
            "effect_size_name",
            "alternative",
        }

    def test_invalid_input_raises(self) -> None:
        with pytest.raises(ValueError):
            paired_t_test([1.0, 2.0], [1.0, 2.0])  # fewer than 3 pairs
        with pytest.raises(ValueError):
            paired_t_test([1.0, 2.0, 3.0], [1.0, 2.0])  # unequal length
        with pytest.raises(ValueError):
            paired_t_test(np.zeros((2, 3)), np.zeros((2, 3)))  # not 1-D
        with pytest.raises(ValueError):
            paired_t_test([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])  # zero variance
        with pytest.raises(ValueError):
            paired_t_test([1.0, 2.0, 3.0], [0.0, 1.0, 2.0], alternative="both")
        with pytest.raises(ValueError):
            paired_t_test([1.0, 2.0, 3.0], [0.0, 1.0, 2.0], confidence=2.0)


class TestWilcoxonSignedRank:
    @pytest.mark.parametrize(("a", "b"), DATASETS)
    def test_matches_scipy(self, a: np.ndarray, b: np.ndarray) -> None:
        result = wilcoxon_signed_rank(a, b)
        reference = st.wilcoxon(a, b, alternative="two-sided", zero_method="wilcox")
        assert result["method"] == "wilcoxon_signed_rank"
        assert result["n"] == a.size
        assert result["statistic"] == pytest.approx(float(reference.statistic))
        assert result["p_value"] == pytest.approx(float(reference.pvalue))
        assert result["effect_size_name"] == "rank_biserial"

    def test_with_zero_differences_and_ties(self) -> None:
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        b = np.array([1.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        result = wilcoxon_signed_rank(a, b)
        reference = st.wilcoxon(a, b, alternative="two-sided", zero_method="wilcox")
        assert result["statistic"] == pytest.approx(float(reference.statistic))
        assert result["p_value"] == pytest.approx(float(reference.pvalue))
        # all non-zero differences are positive -> rank-biserial = 1
        assert result["effect_size"] == pytest.approx(1.0)

    def test_one_sided_and_correction(self) -> None:
        a, b = DATASETS[1]
        result = wilcoxon_signed_rank(a, b, alternative="greater", correction=True)
        reference = st.wilcoxon(
            a, b, alternative="greater", zero_method="wilcox", correction=True
        )
        assert result["statistic"] == pytest.approx(float(reference.statistic))
        assert result["p_value"] == pytest.approx(float(reference.pvalue))

    def test_nan_pairs_excluded(self) -> None:
        a = np.array([1.0, np.nan, 3.0, 4.0, 6.0])
        b = np.array([0.0, 2.0, 2.0, np.nan, 5.0])
        result = wilcoxon_signed_rank(a, b)
        assert result["n"] == 3

    def test_invalid_input_raises(self) -> None:
        with pytest.raises(ValueError):
            wilcoxon_signed_rank([1.0, 2.0], [1.0, 2.0])
        with pytest.raises(ValueError):
            wilcoxon_signed_rank([1.0, 2.0, 3.0], [0.0, 1.0, 2.0], zero_method="bad")
        with pytest.raises(ValueError):
            wilcoxon_signed_rank([1.0, 2.0, 3.0], [0.0, 1.0, 2.0], alternative="both")


class TestNormalityCheck:
    def test_matches_scipy_shapiro(self) -> None:
        values = np.array([1.0, 2.0, 2.5, 3.0, 4.0, 5.0, 5.5, 6.0])
        result = normality_check(values)
        reference = st.shapiro(values)
        assert result["method"] == "shapiro_wilk"
        assert result["n"] == values.size
        assert result["statistic"] == pytest.approx(float(reference.statistic))
        assert result["p_value"] == pytest.approx(float(reference.pvalue))
        assert isinstance(result["normal_at_0_05"], bool)

    def test_nan_excluded(self) -> None:
        result = normality_check([1.0, 2.0, np.nan, 3.0])
        assert result["n"] == 3

    def test_small_sample_returns_none(self) -> None:
        result = normality_check([1.0, 2.0])
        assert result["n"] == 2
        assert np.isnan(result["statistic"])
        assert result["normal_at_0_05"] is None


class TestPairedSummary:
    def test_contains_parametric_and_bootstrap_results(self) -> None:
        a, b = DATASETS[0]
        summary = paired_summary(
            a, b, bootstrap={"n_resamples": 400, "seed": 20260422, "confidence": 0.95}
        )
        assert summary["method"] == "paired_t_test"
        assert summary["n"] == a.size
        assert summary["bootstrap_ci_low"] <= summary["mean_diff"] <= summary["bootstrap_ci_high"]
        assert summary["bootstrap"]["n_resamples"] == 400
        assert set(summary["wilcoxon"]) >= {"statistic", "p_value", "effect_size"}
        assert summary["normality"]["method"] == "shapiro_wilk"

    def test_without_bootstrap_omits_bootstrap_keys(self) -> None:
        a, b = DATASETS[0]
        summary = paired_summary(a, b)
        assert "bootstrap" not in summary
        assert "bootstrap_ci_low" not in summary

    def test_accepts_config_like_object(self) -> None:
        class BootstrapSettings:
            n_resamples = 200
            confidence = 0.9
            seed = 7
            method = "percentile"

        a, b = DATASETS[0]
        summary = paired_summary(a, b, bootstrap=BootstrapSettings())
        assert summary["bootstrap"]["n_resamples"] == 200
        assert summary["bootstrap"]["confidence"] == 0.9
