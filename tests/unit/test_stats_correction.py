"""Holm / Benjamini–Hochberg adjustment tests against hand-computed examples."""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.stats.correction import benjamini_hochberg, holm_bonferroni, reject


class TestHolmBonferroni:
    def test_wikipedia_example(self) -> None:
        p_values = [0.01, 0.02, 0.03, 0.04, 0.05]
        expected = [0.05, 0.08, 0.09, 0.09, 0.09]
        result = holm_bonferroni(p_values)
        assert result == pytest.approx(expected)

    def test_unsorted_input_maps_back_to_original_order(self) -> None:
        p_values = [0.05, 0.01, 0.04, 0.03, 0.02]
        expected = [0.09, 0.05, 0.09, 0.09, 0.08]
        assert holm_bonferroni(p_values) == pytest.approx(expected)

    def test_capped_at_one(self) -> None:
        result = holm_bonferroni([0.9, 0.95])
        assert np.all(result <= 1.0)
        assert result == pytest.approx([1.0, 1.0])

    def test_monotone_in_sorted_order(self) -> None:
        p_values = np.array([0.001, 0.02, 0.2, 0.5, 0.99])
        adjusted = holm_bonferroni(p_values)
        assert np.all(np.diff(adjusted) >= -1e-15)
        assert np.all(adjusted >= p_values - 1e-15)

    def test_empty_input(self) -> None:
        result = holm_bonferroni([])
        assert result.shape == (0,)

    def test_invalid_input_raises(self) -> None:
        with pytest.raises(ValueError):
            holm_bonferroni([0.1, np.nan])
        with pytest.raises(ValueError):
            holm_bonferroni([0.1, 1.2])
        with pytest.raises(ValueError):
            holm_bonferroni([-0.1, 0.2])
        with pytest.raises(ValueError):
            holm_bonferroni([[0.1, 0.2]])


class TestBenjaminiHochberg:
    def test_hand_computed_example(self) -> None:
        # m = 6; sorted p * m / rank = .006, .024, .078, .0615, .0504, .06
        # descending cumulative minimum -> .006, .024, .0504, .0504, .0504, .06
        p_values = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06]
        expected = [0.006, 0.024, 0.0504, 0.0504, 0.0504, 0.06]
        assert benjamini_hochberg(p_values) == pytest.approx(expected)

    def test_wikipedia_uniform_example(self) -> None:
        # For p = 0.01 ... 0.05 with m = 5 the BH-adjusted values are all 0.05.
        p_values = [0.01, 0.02, 0.03, 0.04, 0.05]
        assert benjamini_hochberg(p_values) == pytest.approx([0.05] * 5)

    def test_unsorted_input_maps_back_to_original_order(self) -> None:
        p_values = [0.05, 0.01, 0.04, 0.03, 0.02]
        sorted_adjusted = benjamini_hochberg([0.01, 0.02, 0.03, 0.04, 0.05])
        result = benjamini_hochberg(p_values)
        assert result[1] == pytest.approx(sorted_adjusted[0])
        assert result[4] == pytest.approx(sorted_adjusted[1])
        assert result[3] == pytest.approx(sorted_adjusted[2])
        assert result[2] == pytest.approx(sorted_adjusted[3])
        assert result[0] == pytest.approx(sorted_adjusted[4])

    def test_monotone_and_capped(self) -> None:
        p_values = np.array([0.4, 0.01, 0.99, 0.03])
        adjusted = benjamini_hochberg(p_values)
        assert np.all(adjusted <= 1.0)
        sorted_adjusted = np.sort(adjusted)
        assert np.all(np.diff(sorted_adjusted) >= -1e-15)

    def test_empty_input(self) -> None:
        assert benjamini_hochberg([]).shape == (0,)

    def test_invalid_input_raises(self) -> None:
        with pytest.raises(ValueError):
            benjamini_hochberg([0.2, np.nan])
        with pytest.raises(ValueError):
            benjamini_hochberg([0.2, 2.0])


class TestReject:
    def test_holm_decisions(self) -> None:
        # adjusted (in original order): [.03, .06, .06] -> only the first rejects
        assert reject([0.01, 0.04, 0.03], alpha=0.05, method="holm").tolist() == [
            True,
            False,
            False,
        ]

    def test_bh_decisions(self) -> None:
        assert reject([0.01, 0.04, 0.03], alpha=0.05, method="bh").tolist() == [
            True,
            True,
            True,
        ]

    def test_unadjusted_comparison(self) -> None:
        assert reject([0.01, 0.04, 0.06], alpha=0.05, method="none").tolist() == [
            True,
            True,
            False,
        ]

    def test_unknown_method_raises(self) -> None:
        with pytest.raises(ValueError):
            reject([0.1, 0.2], method="bonferroni-ish")

    def test_invalid_alpha_raises(self) -> None:
        with pytest.raises(ValueError):
            reject([0.1, 0.2], alpha=1.0)
        with pytest.raises(ValueError):
            reject([0.1, 0.2], alpha=0.0)
