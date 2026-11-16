"""Variance-component and between-subject variability tests."""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.data.dataset import TransferCube
from acousticbench.measurements.variability import (
    inter_subject_variability,
    variability_by_device,
    variance_components,
)
from acousticbench.stats.bands import Band
from acousticbench.types import DEVICES

FREQS = np.array([500.0, 1000.0, 2000.0, 4000.0])
WIDE_BAND_LABEL = "500–4000 Hz"
WIDE_BAND = Band(WIDE_BAND_LABEL, center_hz=1414.213562, low_hz=500.0, high_hz=4000.0)
VARIABILITY_COLUMNS = [
    "band",
    "band_center_hz",
    "device_code",
    "device",
    "family",
    "coupling",
    "condition",
    "n_subjects",
    "n_subjects_complete",
    "mean_level_db",
    "sd_between_subject_db",
    "iqr_db",
    "range_db",
    "cv_db",
    "between_subject_variance_db2",
    "within_subject_variance_db2",
    "icc_1_1",
]


def make_cube(
    levels_db: np.ndarray,
    *,
    kind: str = "transfer",
    devices=DEVICES[:2],
    subjects=(1, 2, 3),
    reinsertions=(1, 2, 3),
    freqs: np.ndarray = FREQS,
) -> TransferCube:
    """Build a labelled cube from dB levels (broadcast to the full shape)."""
    shape = (freqs.size, len(devices), len(subjects), len(reinsertions))
    levels = np.broadcast_to(np.asarray(levels_db, dtype=float), shape).copy()
    if kind == "transfer":
        values = (10.0 ** (levels / 20.0)).astype(complex)
    else:
        values = levels.astype(float)
    return TransferCube(
        values=values,
        valid=np.ones(shape, dtype=bool),
        freq_hz=np.asarray(freqs, dtype=float),
        devices=tuple(devices),
        subjects=np.asarray(subjects, dtype=int),
        reinsertions=np.asarray(reinsertions, dtype=int),
        unit="Pa" if kind == "transfer" else "dB",
        unit_label="Pa" if kind == "transfer" else "dB",
        name=f"synthetic-{kind}",
        kind=kind,
    )


class TestVarianceComponents:
    def test_hand_computed_example(self) -> None:
        # subject means 10, 12, 14, 16; within-subject pattern (-0.5, 0, +0.5)
        matrix = np.array(
            [
                [9.5, 10.0, 10.5],
                [11.5, 12.0, 12.5],
                [13.5, 14.0, 14.5],
                [15.5, 16.0, 16.5],
            ]
        )
        result = variance_components(matrix)
        assert result["n_subjects"] == 4
        assert result["n_subjects_dropped"] == 0
        assert result["n_repeats"] == 3
        assert result["grand_mean"] == pytest.approx(13.0)
        assert result["ss_between"] == pytest.approx(60.0)
        assert result["ss_within"] == pytest.approx(2.0)
        assert result["df_between"] == 3
        assert result["df_within"] == 8
        assert result["ms_between"] == pytest.approx(20.0)
        assert result["ms_within"] == pytest.approx(0.25)
        assert result["between_subject_variance"] == pytest.approx((20.0 - 0.25) / 3.0)
        assert result["within_subject_variance"] == pytest.approx(0.25)
        assert result["icc_1_1"] == pytest.approx(19.75 / 20.5)
        # ICC(1,1) equals sigma2_b / (sigma2_b + sigma2_w)
        sigma_b = result["between_subject_variance"]
        sigma_w = result["within_subject_variance"]
        assert result["icc_1_1"] == pytest.approx(sigma_b / (sigma_b + sigma_w))

    def test_zero_within_variance_gives_icc_one(self) -> None:
        matrix = np.array(
            [
                [10.0, 10.0, 10.0],
                [12.0, 12.0, 12.0],
                [14.0, 14.0, 14.0],
            ]
        )
        result = variance_components(matrix)
        assert result["within_subject_variance"] == pytest.approx(0.0)
        assert result["between_subject_variance"] == pytest.approx(4.0)
        assert result["icc_1_1"] == pytest.approx(1.0)

    def test_nan_subjects_dropped_and_counted(self) -> None:
        matrix = np.array(
            [
                [9.5, 10.0, 10.5],
                [11.5, np.nan, 12.5],  # dropped
                [13.5, 14.0, 14.5],
                [15.5, 16.0, 16.5],
            ]
        )
        result = variance_components(matrix)
        assert result["n_subjects"] == 3
        assert result["n_subjects_dropped"] == 1
        assert result["ss_within"] == pytest.approx(1.5)
        assert result["ms_within"] == pytest.approx(0.25)

    def test_all_nan_raises(self) -> None:
        with pytest.raises(ValueError):
            variance_components(np.full((4, 3), np.nan))

    def test_invalid_shapes_raise(self) -> None:
        with pytest.raises(ValueError):
            variance_components([1.0, 2.0, 3.0])
        with pytest.raises(ValueError):
            variance_components(np.zeros((4, 1)))
        with pytest.raises(ValueError):
            variance_components(np.zeros((1, 3)))


class TestInterSubjectVariability:
    def _levels(self) -> np.ndarray:
        # device 0: subject constants 0, 2, 4 dB -> mean 2, sd 2, iqr 2, range 4
        levels = np.zeros((FREQS.size, 2, 3, 3))
        levels[:, 0, :, :] = np.array([0.0, 2.0, 4.0])[None, :, None]
        levels[:, 1, :, :] = 10.0
        return levels

    def test_synthetic_known_values(self) -> None:
        cube = make_cube(self._levels())
        result = inter_subject_variability(cube, (WIDE_BAND,))
        assert list(result.columns) == VARIABILITY_COLUMNS
        assert len(result) == 2
        device_zero = result.loc[result["device_code"] == 1].iloc[0]
        assert device_zero["n_subjects"] == 3
        assert device_zero["n_subjects_complete"] == 3
        assert device_zero["mean_level_db"] == pytest.approx(2.0)
        assert device_zero["sd_between_subject_db"] == pytest.approx(2.0)
        assert device_zero["iqr_db"] == pytest.approx(2.0)
        assert device_zero["range_db"] == pytest.approx(4.0)
        assert device_zero["cv_db"] == pytest.approx(100.0)
        assert device_zero["within_subject_variance_db2"] == pytest.approx(0.0)
        assert device_zero["between_subject_variance_db2"] == pytest.approx(4.0)
        assert device_zero["icc_1_1"] == pytest.approx(1.0)

    def test_metadata_and_icc_matches_variance_components(self) -> None:
        levels = self._levels()
        cube = make_cube(levels)
        result = inter_subject_variability(cube, (WIDE_BAND,))
        assert set(result["band"]) == {WIDE_BAND_LABEL}
        assert set(result["family"]) == {"closed_earmold"}
        assert set(result["coupling"]) == {"earmold"}
        expected = variance_components(levels[0, 0, :, :])["icc_1_1"]
        device_zero = result.loc[result["device_code"] == 1].iloc[0]
        assert device_zero["icc_1_1"] == pytest.approx(expected, abs=1e-12)

    def test_level_cube_path(self) -> None:
        transfer_cube = make_cube(self._levels())
        level_cube = make_cube(self._levels(), kind="level_db")
        from_transfer = inter_subject_variability(transfer_cube, (WIDE_BAND,))
        from_levels = inter_subject_variability(level_cube, (WIDE_BAND,))
        assert np.allclose(
            from_transfer["mean_level_db"].to_numpy(),
            from_levels["mean_level_db"].to_numpy(),
            atol=1e-9,
        )
        assert np.allclose(
            from_transfer["sd_between_subject_db"].to_numpy(),
            from_levels["sd_between_subject_db"].to_numpy(),
            atol=1e-9,
        )

    def test_invalid_input_raises(self) -> None:
        cube = make_cube(self._levels())
        with pytest.raises(ValueError):
            inter_subject_variability(cube, ())
        with pytest.raises(TypeError):
            inter_subject_variability(cube, ("not a band",))  # type: ignore[arg-type]


class TestVariabilityByDevice:
    def test_default_band_and_columns(self) -> None:
        levels = np.zeros((FREQS.size, 2, 3, 3))
        levels[:, 0, :, :] = np.array([0.0, 2.0, 4.0])[None, :, None]
        cube = make_cube(levels)
        result = variability_by_device(cube)
        assert list(result.columns) == VARIABILITY_COLUMNS
        assert len(result) == 2
        assert set(result["band"]) == {WIDE_BAND_LABEL}

    def test_custom_band(self) -> None:
        cube = make_cube(np.zeros((FREQS.size, 2, 3, 3)))
        result = variability_by_device(cube, band_hz=(1000.0, 2000.0))
        assert set(result["band"]) == {"1000–2000 Hz"}
        assert len(result) == 2

    def test_band_outside_axis_raises(self) -> None:
        cube = make_cube(np.zeros((FREQS.size, 2, 3, 3)))
        with pytest.raises(ValueError):
            variability_by_device(cube, band_hz=(8000.0, 16000.0))
