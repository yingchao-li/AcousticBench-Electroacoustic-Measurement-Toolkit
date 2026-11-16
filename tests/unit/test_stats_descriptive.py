"""Numerical tests for descriptive statistics (hand-computed values)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from acousticbench.stats.descriptive import describe_array, subject_means, summarize_layout


class TestDescribeArray:
    def test_known_values_with_nan(self) -> None:
        result = describe_array([1.0, 2.0, 3.0, np.nan])
        assert result["n"] == 3
        assert result["mean"] == pytest.approx(2.0)
        assert result["sd"] == pytest.approx(1.0)  # ddof=1
        assert result["median"] == pytest.approx(2.0)
        assert result["iqr"] == pytest.approx(1.0)
        assert result["min"] == pytest.approx(1.0)
        assert result["max"] == pytest.approx(3.0)
        assert result["se"] == pytest.approx(1.0 / np.sqrt(3.0))
        # Student-t interval of the mean: 2 ± t_{0.975,2} * 1/sqrt(3)
        from scipy.stats import t

        half_width = t.ppf(0.975, 2) / np.sqrt(3.0)
        assert result["ci_low"] == pytest.approx(2.0 - half_width)
        assert result["ci_high"] == pytest.approx(2.0 + half_width)

    def test_all_invalid_returns_zero_n_and_nan(self) -> None:
        result = describe_array([np.nan, np.inf, -np.inf])
        assert result["n"] == 0
        for key in ("mean", "sd", "median", "iqr", "min", "max", "se", "ci_low", "ci_high"):
            assert np.isnan(result[key]), key

    def test_single_observation(self) -> None:
        result = describe_array([42.0])
        assert result["n"] == 1
        assert result["mean"] == 42.0
        assert np.isnan(result["sd"])
        assert np.isnan(result["se"])

    def test_sd_is_ddof_one(self) -> None:
        result = describe_array([1.0, 2.0, 3.0, 4.0])
        assert result["sd"] == pytest.approx(np.sqrt(5.0 / 3.0))

    def test_confidence_validation(self) -> None:
        with pytest.raises(ValueError):
            describe_array([1.0, 2.0], confidence=1.5)


class TestSummarizeLayout:
    def test_grouped_hand_computed(self) -> None:
        frame = pd.DataFrame(
            {
                "device": ["A"] * 4 + ["B"] * 4,
                "value": [1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0],
            }
        )
        result = summarize_layout(frame, value_col="value", group_cols=["device"])
        assert list(result.columns) == [
            "device",
            "n",
            "mean",
            "sd",
            "median",
            "iqr",
            "p05",
            "p25",
            "p75",
            "p95",
            "min",
            "max",
        ]
        row = result.loc[result["device"] == "A"].iloc[0]
        assert row["n"] == 4
        assert row["mean"] == pytest.approx(2.5)
        assert row["sd"] == pytest.approx(np.std([1, 2, 3, 4], ddof=1))
        assert row["median"] == pytest.approx(2.5)
        assert row["iqr"] == pytest.approx(1.5)
        assert row["p05"] == pytest.approx(np.percentile([1, 2, 3, 4], 5))
        assert row["p25"] == pytest.approx(1.75)
        assert row["p75"] == pytest.approx(3.25)
        assert row["p95"] == pytest.approx(np.percentile([1, 2, 3, 4], 95))
        assert row["min"] == 1.0
        assert row["max"] == 4.0

    def test_nan_values_are_excluded_from_statistics(self) -> None:
        frame = pd.DataFrame({"group": ["x", "x", "x"], "value": [1.0, np.nan, 3.0]})
        result = summarize_layout(frame, value_col="value", group_cols=["group"])
        row = result.iloc[0]
        assert row["n"] == 2
        assert row["mean"] == pytest.approx(2.0)
        assert row["sd"] == pytest.approx(np.sqrt(2.0))

    def test_missing_columns_raise(self) -> None:
        frame = pd.DataFrame({"value": [1.0, 2.0]})
        with pytest.raises(ValueError):
            summarize_layout(frame, value_col="value", group_cols=["missing"])
        with pytest.raises(ValueError):
            summarize_layout(frame, value_col="nope", group_cols=[])


class TestSubjectMeans:
    def test_collapses_reinsertions_to_one_row_per_subject(self) -> None:
        frame = pd.DataFrame(
            {
                "device_code": [1] * 6,
                "subject": [1, 1, 1, 2, 2, 2],
                "reinsertion": [1, 2, 3, 1, 2, 3],
                "level_db": [1.0, 2.0, np.nan, 10.0, 10.0, 10.0],
            }
        )
        result = subject_means(frame, value_col="level_db")
        assert len(result) == 2
        assert "reinsertion" not in result.columns
        assert list(result.columns) == ["device_code", "subject", "level_db", "n_reinsertions"]
        first = result.loc[result["subject"] == 1].iloc[0]
        assert first["level_db"] == pytest.approx(1.5)
        assert first["n_reinsertions"] == 2
        second = result.loc[result["subject"] == 2].iloc[0]
        assert second["level_db"] == pytest.approx(10.0)
        assert second["n_reinsertions"] == 3

    def test_subject_without_finite_value_is_dropped(self) -> None:
        frame = pd.DataFrame(
            {
                "device_code": [1, 1, 1, 1],
                "subject": [1, 1, 2, 2],
                "reinsertion": [1, 2, 1, 2],
                "level_db": [1.0, 2.0, np.nan, np.nan],
            }
        )
        result = subject_means(frame, value_col="level_db")
        assert result["subject"].tolist() == [1]

    def test_multiple_group_columns(self) -> None:
        frame = pd.DataFrame(
            {
                "device_code": [1, 1, 2, 2],
                "band": ["500 Hz"] * 4,
                "subject": [1, 1, 1, 1],
                "reinsertion": [1, 2, 1, 2],
                "level_db": [1.0, 3.0, 10.0, 20.0],
            }
        )
        result = subject_means(frame, value_col="level_db", group_cols=("device_code", "band"))
        assert len(result) == 2
        assert result.loc[result["device_code"] == 1, "level_db"].iloc[0] == pytest.approx(2.0)
        assert result.loc[result["device_code"] == 2, "level_db"].iloc[0] == pytest.approx(15.0)

    def test_invalid_columns_raise(self) -> None:
        frame = pd.DataFrame({"subject": [1], "level_db": [1.0]})
        with pytest.raises(ValueError):
            subject_means(frame, value_col="level_db", subject_col="missing")
        with pytest.raises(ValueError):
            subject_means(frame, value_col="missing")
