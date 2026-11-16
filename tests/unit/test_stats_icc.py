"""ICC(2,1) tests against a hand-computed two-way ANOVA example."""

from __future__ import annotations

import numpy as np
import pytest
import scipy.stats as st

from acousticbench.stats.icc import IccResult, icc_2_1

# Hand-computed two-way random-effects example (n = 4 subjects, k = 2 raters):
#   grand mean 3.5, row means 1.5, 3, 4, 5.5, column means 2.5, 4.5
#   SS_R = 17, SS_C = 8, SS_T = 26 -> SS_E = 1
#   MS_R = 17/3, MS_C = 8, MS_E = 1/3, df = (3, 3)
#   ICC(2,1) = (17/3 - 1/3) / (17/3 + 1/3 + 2*(8 - 1/3)/4) = 80/147
HAND_MATRIX = np.array(
    [
        [1.0, 2.0],
        [2.0, 4.0],
        [3.0, 5.0],
        [4.0, 7.0],
    ]
)
HAND_ICC = 32.0 / 59.0


def _reference_icc_2_1(matrix: np.ndarray) -> dict[str, float]:
    """Independent implementation of the two-way ANOVA formulas."""
    n, k = matrix.shape
    grand = matrix.mean()
    ss_rows = k * ((matrix.mean(axis=1) - grand) ** 2).sum()
    ss_columns = n * ((matrix.mean(axis=0) - grand) ** 2).sum()
    ss_total = ((matrix - grand) ** 2).sum()
    ss_error = ss_total - ss_rows - ss_columns
    ms_rows = ss_rows / (n - 1)
    ms_columns = ss_columns / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))
    icc = (ms_rows - ms_error) / (
        ms_rows + (k - 1) * ms_error + k * (ms_columns - ms_error) / n
    )
    return {
        "icc": icc,
        "ms_rows": ms_rows,
        "ms_columns": ms_columns,
        "ms_error": ms_error,
        "f_value": ms_rows / ms_error,
        "df1": n - 1,
        "df2": (n - 1) * (k - 1),
    }


class TestHandExample:
    def test_hand_computed_values(self) -> None:
        result = icc_2_1(HAND_MATRIX)
        assert isinstance(result, IccResult)
        assert result.model == "ICC(2,1)"
        assert result.icc == pytest.approx(HAND_ICC, abs=1e-12)
        assert result.f_value == pytest.approx(17.0, abs=1e-12)
        assert result.df1 == 3
        assert result.df2 == 3
        assert result.n_subjects == 4
        assert result.n_raters == 2
        assert result.p_value == pytest.approx(float(st.f.sf(17.0, 3, 3)), abs=1e-12)

    def test_to_dict(self) -> None:
        payload = icc_2_1(HAND_MATRIX).to_dict()
        assert set(payload) == {
            "icc",
            "f_value",
            "df1",
            "df2",
            "p_value",
            "n_subjects",
            "n_raters",
            "model",
            "ci_low",
            "ci_high",
        }


class TestReferenceFormula:
    @pytest.mark.parametrize(
        "matrix",
        [
            np.array([[1.0, 2.0, 3.0], [2.0, 2.5, 3.5], [4.0, 5.0, 3.0], [2.0, 1.0, 1.5]]),
            np.array([[10.0, 11.0], [9.0, 8.0], [12.0, 13.0], [7.0, 6.0], [11.0, 10.0]]),
        ],
    )
    def test_matches_independent_anova(self, matrix: np.ndarray) -> None:
        expected = _reference_icc_2_1(matrix)
        result = icc_2_1(matrix)
        assert result.icc == pytest.approx(expected["icc"], abs=1e-12)
        assert result.f_value == pytest.approx(expected["f_value"], abs=1e-12)
        assert result.df1 == expected["df1"]
        assert result.df2 == expected["df2"]
        assert result.p_value == pytest.approx(
            float(st.f.sf(expected["f_value"], expected["df1"], expected["df2"])), abs=1e-12
        )


class TestMissingData:
    def test_incomplete_subjects_dropped_and_counted(self) -> None:
        matrix = np.vstack([HAND_MATRIX, [np.nan, 3.0], [2.0, np.nan]])
        result = icc_2_1(matrix)
        assert result.n_subjects == 4
        assert result.icc == pytest.approx(HAND_ICC, abs=1e-12)

    def test_too_few_complete_subjects_raise(self) -> None:
        matrix = np.array([[np.nan, 1.0], [2.0, np.nan], [3.0, 3.0]])
        with pytest.raises(ValueError):
            icc_2_1(matrix)


class TestReliability:
    def test_perfect_reliability(self) -> None:
        matrix = np.array(
            [
                [1.0, 1.0, 1.0],
                [2.0, 2.0, 2.0],
                [3.0, 3.0, 3.0],
                [4.0, 4.0, 4.0],
            ]
        )
        result = icc_2_1(matrix)
        assert result.icc == pytest.approx(1.0, abs=1e-12)
        assert result.f_value == float("inf")
        assert result.p_value == 0.0

    def test_all_identical_matrix_is_undefined(self) -> None:
        matrix = np.array([[5.0, 5.0], [5.0, 5.0], [5.0, 5.0]])
        result = icc_2_1(matrix)
        assert np.isnan(result.icc)
        assert np.isnan(result.f_value)
        assert np.isnan(result.p_value)

    def test_low_reliability_is_small(self) -> None:
        # raters disagree strongly within subjects -> ICC well below 1
        matrix = np.array(
            [
                [0.0, 10.0],
                [10.0, 0.0],
                [1.0, 9.0],
                [9.0, 1.0],
            ]
        )
        result = icc_2_1(matrix)
        assert result.icc < 0.5


class TestBootstrapCi:
    def test_ci_contains_estimate_and_is_deterministic(self) -> None:
        first = icc_2_1(HAND_MATRIX, confidence=0.95, n_resamples=300, seed=20260422)
        second = icc_2_1(HAND_MATRIX, confidence=0.95, n_resamples=300, seed=20260422)
        assert first.ci_low is not None and first.ci_high is not None
        assert first.ci_low <= first.icc <= first.ci_high
        assert (first.ci_low, first.ci_high) == (second.ci_low, second.ci_high)

    def test_invalid_settings_raise(self) -> None:
        with pytest.raises(ValueError):
            icc_2_1(HAND_MATRIX, confidence=1.0)
        with pytest.raises(ValueError):
            icc_2_1(HAND_MATRIX, confidence=0.95, n_resamples=5)

    def test_frozen_result(self) -> None:
        from dataclasses import FrozenInstanceError

        result = icc_2_1(HAND_MATRIX)
        with pytest.raises(FrozenInstanceError):
            result.icc = 0.5  # type: ignore[misc]


class TestInvalidInput:
    def test_wrong_dimensions_raise(self) -> None:
        with pytest.raises(ValueError):
            icc_2_1([1.0, 2.0, 3.0])
        with pytest.raises(ValueError):
            icc_2_1(np.array([[1.0], [2.0], [3.0]]))  # one rater
        with pytest.raises(ValueError):
            icc_2_1(np.array([[1.0, 2.0]]))  # one subject

    def test_non_numeric_raises(self) -> None:
        with pytest.raises(ValueError):
            icc_2_1(np.array([["a", "b"], ["c", "d"]]))
