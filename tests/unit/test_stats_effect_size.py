"""Exact hand-computed effect-size tests."""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.stats.effect_size import cohen_d, cohen_dz, hedges_g, rank_biserial


class TestCohenDz:
    def test_exact_example(self) -> None:
        # mean = 2, sample sd = 1  ->  dz = 2
        assert cohen_dz([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_negative_effect(self) -> None:
        assert cohen_dz([-1.0, -2.0, -3.0]) == pytest.approx(-2.0)

    def test_nan_is_excluded(self) -> None:
        assert cohen_dz([1.0, 2.0, 3.0, np.nan]) == pytest.approx(2.0)

    def test_matches_closed_form(self) -> None:
        differences = np.array([0.5, -1.25, 2.0, 3.5, 0.75])
        expected = np.mean(differences) / np.std(differences, ddof=1)
        assert cohen_dz(differences) == pytest.approx(expected)

    def test_too_few_values_raise(self) -> None:
        with pytest.raises(ValueError):
            cohen_dz([1.0])
        with pytest.raises(ValueError):
            cohen_dz([np.nan, np.nan])

    def test_zero_variance_raises(self) -> None:
        with pytest.raises(ValueError):
            cohen_dz([2.0, 2.0, 2.0])


class TestCohenD:
    def test_exact_example(self) -> None:
        # means 2 and 3, both sample sd = 1, pooled sd = 1  ->  d = -1
        assert cohen_d([1.0, 2.0, 3.0], [2.0, 3.0, 4.0]) == pytest.approx(-1.0)

    def test_pooled_sd_formula(self) -> None:
        a = np.array([1.0, 2.0, 4.0, 8.0])
        b = np.array([0.0, 3.0, 3.5, 4.0, 9.0])
        n_a, n_b = a.size, b.size
        pooled = np.sqrt(
            ((n_a - 1) * np.var(a, ddof=1) + (n_b - 1) * np.var(b, ddof=1)) / (n_a + n_b - 2)
        )
        expected = (np.mean(a) - np.mean(b)) / pooled
        assert cohen_d(a, b) == pytest.approx(expected)

    def test_too_few_values_raise(self) -> None:
        with pytest.raises(ValueError):
            cohen_d([1.0], [1.0, 2.0, 3.0])

    def test_zero_pooled_variance_raises(self) -> None:
        with pytest.raises(ValueError):
            cohen_d([2.0, 2.0, 2.0], [2.0, 2.0, 2.0])


class TestHedgesG:
    def test_exact_small_sample_correction(self) -> None:
        # n = 3 -> df = 2, correction J = 1 - 3/(4*2 - 1) = 4/7
        # dz = 2  ->  g = 8/7
        assert hedges_g([1.0, 2.0, 3.0]) == pytest.approx(8.0 / 7.0)

    def test_matches_closed_form(self) -> None:
        differences = np.array([-2.0, -1.0, 0.5, 1.5, 3.0])
        dz = np.mean(differences) / np.std(differences, ddof=1)
        correction = 1.0 - 3.0 / (4.0 * (differences.size - 1) - 1.0)
        assert hedges_g(differences) == pytest.approx(dz * correction)

    def test_too_few_values_raise(self) -> None:
        with pytest.raises(ValueError):
            hedges_g([1.0])


class TestRankBiserial:
    def test_all_positive_yields_one(self) -> None:
        assert rank_biserial([1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(1.0)

    def test_all_negative_yields_minus_one(self) -> None:
        assert rank_biserial([-1.0, -2.0, -3.0]) == pytest.approx(-1.0)

    def test_hand_computed_example(self) -> None:
        # ranks of |d|: 1, 2, 3, 4, 5.  W+ = 1+2+3+4 = 10, W- = 5.
        # r = (10 - 5) / 15 = 1/3
        assert rank_biserial([1.0, 2.0, 3.0, 4.0, -5.0]) == pytest.approx(1.0 / 3.0)

    def test_ties_use_average_ranks(self) -> None:
        # |d| = 1, 1, 2, 2 -> average ranks 1.5, 1.5, 3.5, 3.5
        # W+ = 1.5 + 3.5 = 5, W- = 1.5 + 3.5 = 5 -> r = 0
        assert rank_biserial([1.0, -1.0, 2.0, -2.0]) == pytest.approx(0.0)

    def test_zero_differences_ignored(self) -> None:
        assert rank_biserial([1.0, 2.0, 0.0, 0.0]) == pytest.approx(1.0)

    def test_all_zero_returns_zero(self) -> None:
        assert rank_biserial([0.0, 0.0, 0.0]) == pytest.approx(0.0)

    def test_matches_scipy_ranksum_relationship(self) -> None:
        # For the two-sided signed-rank test, scipy's statistic W satisfies
        # W = W+ - n(n+1)/4 after centring; here we verify the rank sums via
        # an independent computation.
        differences = np.array([0.5, -1.0, 2.0, -3.0, 4.5, -0.25])
        nonzero = differences[differences != 0.0]
        order = np.argsort(np.abs(nonzero))
        ranks = np.empty(nonzero.size, dtype=float)
        ranks[order] = np.arange(1, nonzero.size + 1)
        positive = ranks[nonzero > 0].sum()
        negative = ranks[nonzero < 0].sum()
        assert rank_biserial(differences) == pytest.approx(
            (positive - negative) / (positive + negative)
        )
