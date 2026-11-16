"""Repeatability tests on synthetic TransferCube data with known SD."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from acousticbench.data.dataset import TransferCube, load_dataset
from acousticbench.stats.bands import Band, octave_bands
from acousticbench.stats.icc import icc_2_1
from acousticbench.measurements.repeatability import (
    extract_levels,
    repeatability_by_device,
    repeatability_summary,
    reinsertion_sd_by_frequency,
)
from acousticbench.types import DEVICES

FREQS = np.array([500.0, 1000.0, 2000.0, 4000.0])
WIDE_BAND = Band("500–4000 Hz", center_hz=1414.213562, low_hz=500.0, high_hz=4000.0)
EXPECTED_SUMMARY_COLUMNS = [
    "band",
    "band_center_hz",
    "device_code",
    "device",
    "family",
    "coupling",
    "condition",
    "n_subjects",
    "median_level_db",
    "sd_reinsertion_db_median",
    "sd_reinsertion_db_p95",
    "repeatability_coefficient_db",
    "icc_2_1",
]


def make_cube(
    levels_db: np.ndarray,
    *,
    valid: np.ndarray | None = None,
    kind: str = "transfer",
    devices=DEVICES[:2],
    subjects=(1, 2, 3),
    reinsertions=(1, 2, 3),
    freqs: np.ndarray = FREQS,
) -> TransferCube:
    """Build a labelled cube from dB levels (constant per frequency if desired)."""
    levels = np.asarray(levels_db, dtype=float)
    shape = (freqs.size, len(devices), len(subjects), len(reinsertions))
    if levels.shape != shape:
        levels = np.broadcast_to(levels, shape).copy()
    if valid is None:
        valid_array = np.ones(shape, dtype=bool)
    else:
        valid_array = np.asarray(valid, dtype=bool)
        if valid_array.shape != shape:
            valid_array = np.broadcast_to(valid_array, shape).copy()
    if kind == "transfer":
        values = (10.0 ** (levels / 20.0)).astype(complex)
    else:
        values = levels.astype(float)
    return TransferCube(
        values=values,
        valid=valid_array,
        freq_hz=np.asarray(freqs, dtype=float),
        devices=tuple(devices),
        subjects=np.asarray(subjects, dtype=int),
        reinsertions=np.asarray(reinsertions, dtype=int),
        unit="Pa" if kind == "transfer" else "dB",
        unit_label="Pa" if kind == "transfer" else "dB",
        name=f"synthetic-{kind}",
        kind=kind,
    )


# levels: device 0 has subject 1 = [0,1,2] dB (SD 1, range 2),
#         device 1 has subject 1 = [0,2,4] dB (SD 2, range 4);
#         all other cells constant across reinsertions.
LEVELS = np.zeros((FREQS.size, 2, 3, 3))
LEVELS[:, 0, 0, :] = [0.0, 1.0, 2.0]
LEVELS[:, 1, 0, :] = [0.0, 2.0, 4.0]
LEVELS[:, :, 1, :] = 10.0
LEVELS[:, :, 2, :] = 5.0


class TestExtractLevels:
    def test_transfer_cube_levels_round_trip(self) -> None:
        cube = make_cube(LEVELS)
        levels = extract_levels(cube, 1.0)
        assert levels.shape == (FREQS.size, 2, 3, 3)
        expected = np.tile(np.array([0.0, 1.0, 2.0]), (FREQS.size, 1))
        assert np.allclose(levels[:, 0, 0, :], expected, atol=1e-9)

    def test_invalid_entries_are_nan(self) -> None:
        valid = np.ones((FREQS.size, 2, 3, 3), dtype=bool)
        valid[:, 0, 0, 2] = False
        cube = make_cube(LEVELS, valid=valid)
        levels = extract_levels(cube, 1.0)
        assert np.all(np.isnan(levels[:, 0, 0, 2]))
        assert np.all(np.isfinite(levels[:, 0, 0, :2]))

    def test_level_cube_is_returned_unchanged(self) -> None:
        cube = make_cube(LEVELS, kind="level_db")
        assert extract_levels(cube, 1.0) == pytest.approx(LEVELS)

    def test_invalid_arguments_raise(self) -> None:
        cube = make_cube(LEVELS)
        with pytest.raises(TypeError):
            extract_levels("not a cube", 1.0)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            extract_levels(cube, 0.0)


class TestReinsertionSdByFrequency:
    def test_known_sd_and_range(self) -> None:
        cube = make_cube(LEVELS)
        result = reinsertion_sd_by_frequency(cube)
        assert list(result.columns) == [
            "frequency_hz",
            "device_code",
            "device",
            "family",
            "coupling",
            "condition",
            "subject",
            "n_reinsertions",
            "sd_db",
            "range_db",
        ]
        assert len(result) == FREQS.size * 2 * 3
        assert set(result["frequency_hz"]) == set(FREQS)
        # device 0, subject 1: levels [0, 1, 2] -> SD 1, range 2
        slice_ = result[(result["device_code"] == 1) & (result["subject"] == 1)]
        assert slice_["sd_db"].to_numpy() == pytest.approx(np.ones(FREQS.size))
        assert slice_["range_db"].to_numpy() == pytest.approx(2.0 * np.ones(FREQS.size))
        assert set(slice_["n_reinsertions"]) == {3}
        # device 1, subject 1: levels [0, 2, 4] -> SD 2, range 4
        slice_ = result[(result["device_code"] == 2) & (result["subject"] == 1)]
        assert slice_["sd_db"].to_numpy() == pytest.approx(2.0 * np.ones(FREQS.size))
        assert slice_["range_db"].to_numpy() == pytest.approx(4.0 * np.ones(FREQS.size))
        # constant cells -> SD 0
        constant = result[(result["device_code"] == 1) & (result["subject"] == 2)]
        assert constant["sd_db"].to_numpy() == pytest.approx(np.zeros(FREQS.size))

    def test_metadata_columns(self) -> None:
        result = reinsertion_sd_by_frequency(make_cube(LEVELS))
        first = result.iloc[0]
        assert first["device_code"] == 1
        assert first["family"] == "closed_earmold"
        assert first["coupling"] == "earmold"
        assert first["condition"] == "reference"

    def test_invalid_reinsertions_reduce_n(self) -> None:
        valid = np.ones((FREQS.size, 2, 3, 3), dtype=bool)
        valid[:, 0, 0, 2] = False  # drop the 2 dB reinsertion of subject 1
        cube = make_cube(LEVELS, valid=valid)
        result = reinsertion_sd_by_frequency(cube)
        slice_ = result[(result["device_code"] == 1) & (result["subject"] == 1)]
        assert set(slice_["n_reinsertions"]) == {2}
        # remaining levels [0, 1] -> SD = sqrt(0.5), range 1
        assert slice_["sd_db"].to_numpy() == pytest.approx(
            np.full(FREQS.size, np.sqrt(0.5))
        )
        assert slice_["range_db"].to_numpy() == pytest.approx(np.ones(FREQS.size))

    def test_single_valid_reinsertion_gives_nan(self) -> None:
        valid = np.ones((FREQS.size, 2, 3, 3), dtype=bool)
        valid[:, 0, 0, 1] = False
        valid[:, 0, 0, 2] = False
        cube = make_cube(LEVELS, valid=valid)
        result = reinsertion_sd_by_frequency(cube)
        slice_ = result[(result["device_code"] == 1) & (result["subject"] == 1)]
        assert np.all(np.isnan(slice_["sd_db"]))
        assert np.all(np.isnan(slice_["range_db"]))
        assert set(slice_["n_reinsertions"]) == {1}


class TestRepeatabilitySummary:
    def test_columns_and_subject_count(self) -> None:
        cube = make_cube(LEVELS)
        result = repeatability_summary(cube, (WIDE_BAND,))
        assert list(result.columns) == EXPECTED_SUMMARY_COLUMNS
        assert len(result) == 2  # one row per device
        assert set(result["n_subjects"]) == {3}
        assert set(result["band"]) == {WIDE_BAND.label}

    def test_known_within_subject_sd_statistics(self) -> None:
        cube = make_cube(LEVELS)
        result = repeatability_summary(cube, (WIDE_BAND,))
        device_zero = result.loc[result["device_code"] == 1].iloc[0]
        # within-subject SDs: subject 1 -> 1.0, subjects 2/3 -> 0.0
        # median = 0, p95 = percentile([0, 0, 1], 95) = 0.95
        assert device_zero["sd_reinsertion_db_median"] == pytest.approx(0.0)
        assert device_zero["sd_reinsertion_db_p95"] == pytest.approx(0.9)
        assert device_zero["repeatability_coefficient_db"] == pytest.approx(0.0)
        # subject band levels: 1.0 (mean of 0,1,2), 10, 5 -> median 5
        assert device_zero["median_level_db"] == pytest.approx(5.0)

    def test_icc_matches_direct_icc_call(self) -> None:
        cube = make_cube(LEVELS)
        result = repeatability_summary(cube, (WIDE_BAND,))
        matrix = LEVELS[0, 0, :, :]
        expected = icc_2_1(matrix).icc
        device_zero = result.loc[result["device_code"] == 1].iloc[0]
        assert device_zero["icc_2_1"] == pytest.approx(expected, abs=1e-12)

    def test_repeatability_coefficient_formula(self) -> None:
        # subject 1 SD = 1 on both devices -> median SD = 1 -> RC = 1.96*sqrt(2)
        cube = make_cube(LEVELS)
        result = repeatability_summary(cube, (WIDE_BAND,))
        # construct a case where every subject has SD 1 (levels -1, 0, 1)
        uniform = np.zeros((FREQS.size, 2, 3, 3))
        uniform[:, :, :, :] = [-1.0, 0.0, 1.0]
        result_uniform = repeatability_summary(make_cube(uniform), (WIDE_BAND,))
        expected = 1.96 * np.sqrt(2.0) * 1.0
        assert np.allclose(
            result_uniform["sd_reinsertion_db_median"].to_numpy(), 1.0
        )
        assert np.allclose(
            result_uniform["repeatability_coefficient_db"].to_numpy(), expected
        )
        # keep the first result meaningful (no assertion error on unused variable)
        assert len(result) == 2

    def test_multiple_bands(self) -> None:
        bands = octave_bands(f_min=500.0, f_max=4000.0)
        cube = make_cube(LEVELS)
        result = repeatability_summary(cube, bands)
        assert len(result) == len(bands) * 2
        assert set(result["band"]) == {band.label for band in bands}

    def test_level_cube_path_gives_same_answer_for_constant_levels(self) -> None:
        transfer_cube = make_cube(LEVELS)
        level_cube = make_cube(LEVELS, kind="level_db")
        from_transfer = repeatability_summary(transfer_cube, (WIDE_BAND,))
        from_levels = repeatability_summary(level_cube, (WIDE_BAND,))
        assert np.allclose(
            from_transfer["median_level_db"].to_numpy(),
            from_levels["median_level_db"].to_numpy(),
            atol=1e-9,
        )
        assert np.allclose(
            from_transfer["sd_reinsertion_db_median"].to_numpy(),
            from_levels["sd_reinsertion_db_median"].to_numpy(),
            atol=1e-9,
        )
        assert np.allclose(
            from_transfer["icc_2_1"].to_numpy(), from_levels["icc_2_1"].to_numpy(), atol=1e-9
        )

    def test_invalid_input_raises(self) -> None:
        cube = make_cube(LEVELS)
        with pytest.raises(ValueError):
            repeatability_summary(cube, ())
        with pytest.raises(TypeError):
            repeatability_summary(cube, ("not a band",))  # type: ignore[arg-type]


class TestRepeatabilityByDevice:
    def test_default_band_and_columns(self) -> None:
        cube = make_cube(LEVELS)
        result = repeatability_by_device(cube)
        assert list(result.columns) == EXPECTED_SUMMARY_COLUMNS
        assert len(result) == 2
        assert set(result["band"]) == {"500–4000 Hz"}
        assert result["band_center_hz"].to_numpy() == pytest.approx(
            np.full(len(result), 1414.213562)
        )

    def test_custom_band_edges(self) -> None:
        cube = make_cube(LEVELS)
        result = repeatability_by_device(cube, band_hz=(1000.0, 2000.0))
        assert set(result["band"]) == {"1000–2000 Hz"}

    def test_band_outside_axis_raises(self) -> None:
        cube = make_cube(LEVELS)
        with pytest.raises(ValueError):
            repeatability_by_device(cube, band_hz=(8000.0, 16000.0))
        with pytest.raises(ValueError):
            repeatability_by_device(cube, band_hz=(2000.0, 1000.0, 3000.0))


@pytest.mark.requires_data
class TestRealDatasetSmoke:
    def test_repeatability_on_measurement_probe_cube(self) -> None:
        dataset = load_dataset(compute_hash=False)
        cube = dataset.get(
            "M_ha2edM", device_codes=[2], freq_range=(500.0, 4000.0)
        )
        band = Band("500–4000 Hz", center_hz=1414.213562, low_hz=500.0, high_hz=4000.0)
        summary = repeatability_summary(cube, (band,))
        assert len(summary) == 1
        row = summary.iloc[0]
        assert 10 <= row["n_subjects"] <= 14  # some sessions are documented NaN
        assert np.isfinite(row["median_level_db"])
        assert np.isfinite(row["sd_reinsertion_db_median"])
        assert row["sd_reinsertion_db_median"] > 0.0
        assert np.isfinite(row["icc_2_1"])
        assert -1.0 <= row["icc_2_1"] <= 1.0
        frequency = reinsertion_sd_by_frequency(cube)
        assert len(frequency) == cube.n_frequencies * cube.n_subjects
        assert {"sd_db", "range_db"}.issubset(frequency.columns)
