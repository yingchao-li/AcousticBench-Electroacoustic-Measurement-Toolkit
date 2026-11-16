"""Unit tests for :mod:`acousticbench.data.dataset`.

Mechanics (shapes, selection, masks, aggregation, tidy frames) are tested on a
session-scoped synthetic dataset that carries the exact documented schema, so
the data-free CI subset still exercises the full dataset abstraction.  The
real-data checks (real NaN layout, audit) are marked ``requires_data``.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from acousticbench.data import load_dataset
from acousticbench.data.dataset import AcousticDataset, TransferCube
from acousticbench.exceptions import DataSelectionError, DataValidationError
from acousticbench.types import (
    CONTAINER_ORDER,
    DEVICE_FREE_FIELD,
    DEVICE_OPEN_EAR,
    N_REINSERTIONS,
    N_SUBJECTS,
    REUR_CONTAINER_KEY,
    THRESHOLD_CONTAINER_KEY,
    TRANSFER_CONTAINER_KEYS,
    Condition,
    Coupling,
)


@pytest.fixture(scope="module")
def cube(small_dataset):
    """A representative transfer cube of the synthetic dataset."""
    return small_dataset.get("M_ha2edM")


# ---------------------------------------------------------------------------
# shapes, axes and metadata
# ---------------------------------------------------------------------------
def test_transfer_cube_shapes_and_axes(small_dataset, cube):
    assert cube.shape == (2049, 14, N_SUBJECTS, N_REINSERTIONS)
    assert cube.n_frequencies == 2049
    assert cube.n_devices == 14
    assert cube.n_subjects == N_SUBJECTS
    assert cube.n_reinsertions == N_REINSERTIONS
    np.testing.assert_array_equal(cube.freq_hz, small_dataset.frequency_hz)
    assert cube.device_codes == tuple(range(1, 15))
    assert tuple(cube.subjects) == tuple(range(1, N_SUBJECTS + 1))
    assert tuple(cube.reinsertions) == (1, 2, 3)
    assert cube.kind == "transfer"
    assert cube.container == "M_ha2edM"
    assert cube.unit == "Pa at 11.2 mV drive"
    assert cube.unit_label == "Pa @ 11.2 mV"
    assert cube.families == (
        "closed_earmold",
        "vented_earmold",
        "nugget_earmold",
        "silicone_earmold",
        "open_dome",
        "tulip_dome",
        "power_dome",
    )
    assert cube.is_empty is False
    assert cube.n_valid == int(cube.valid.sum())
    assert 0.0 < cube.valid_fraction < 1.0
    assert "M_ha2edM" in repr(cube)
    assert "shape" in cube.describe()


def test_threshold_cube(small_dataset):
    threshold = small_dataset.threshold()
    assert threshold.shape == (6, 14, N_SUBJECTS, N_REINSERTIONS)
    assert threshold.kind == "threshold_dbv"
    assert threshold.axis_name == "threshold_frequency_hz"
    np.testing.assert_allclose(threshold.freq_hz, small_dataset.threshold_frequency_hz)
    np.testing.assert_allclose(threshold.freq_hz, [125, 250, 500, 750, 1000, 2000])
    assert threshold.unit == "dBV"
    assert threshold.valid.all()


def test_reur_cube_single_insertion(small_dataset):
    reur = small_dataset.reur()
    assert reur.shape == (2049, 1, N_SUBJECTS, 1)
    assert reur.devices == (DEVICE_OPEN_EAR,)
    assert tuple(reur.reinsertions) == (1,)
    assert reur.metadata["single_insertion"] is True
    assert reur.valid.all()
    # Selections that are not meaningful for a single-device cube are ignored.
    assert small_dataset.reur(device_codes=[2], conditions=[Condition.MEASUREMENT]).shape == reur.shape


def test_structural_mask(small_dataset):
    expected = {
        "M_ha2edM": 7,
        "M_ha2edR": 8,
        "M_ha2haf": 14,
        "M_ls2edM": 7,
        "M_ls2edR": 8,
        "M_thr_ha": 14,
        "M_REUR": 14,
    }
    for key, count in expected.items():
        mask = small_dataset.structural_mask(key)
        assert mask.shape == (14,)
        assert mask.dtype == bool
        assert int(mask.sum()) == count


def test_spec_and_values_lookups(small_dataset):
    assert small_dataset.spec("M_ha2edM").key == "M_ha2edM"
    with pytest.raises(KeyError):
        small_dataset.spec("nope")
    assert small_dataset.values("M_ha2edM") is small_dataset.raw.variables["M_ha2edM"]
    with pytest.raises(KeyError):
        small_dataset.values("nope")
    assert small_dataset.containers == CONTAINER_ORDER


# ---------------------------------------------------------------------------
# validity masks (structural AND measured NaN)
# ---------------------------------------------------------------------------
def test_valid_mask_reference_condition_is_structural(small_dataset, cube):
    # M_ha2edM: reference-condition device indices 0, 2, 4, ... are structurally invalid.
    assert not cube.valid[:, 0, :, :].any()
    assert not cube.valid[:, 2, :, :].any()
    # Device index 3 (code 4) is a measurement-condition device without planted NaNs.
    assert cube.valid[:, 3, :, :].all()


def test_valid_mask_marks_planted_nan_sessions(small_dataset, cube, small_nan_sessions):
    device, subject, reinsertion = small_nan_sessions["M_ha2edM"][0]
    assert not cube.valid[:, device, subject, reinsertion].any()
    # The other reinsertions of the same subject/session are unaffected.
    assert cube.valid[:, device, subject, 1].all()
    assert cube.valid[:, device, subject, 2].all()


def test_valid_mask_matches_validity_module(small_dataset):
    from acousticbench.data.validity import build_valid_mask

    for key in TRANSFER_CONTAINER_KEYS:
        expected = build_valid_mask(small_dataset.values(key), small_dataset.spec(key))
        np.testing.assert_array_equal(small_dataset.get(key).valid, expected)


def test_masked_replaces_invalid_values(cube):
    masked = cube.masked
    assert masked.shape == cube.shape
    assert np.isnan(masked[~cube.valid]).all()
    np.testing.assert_array_equal(masked[cube.valid], cube.values[cube.valid])


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------
def test_select_by_condition(small_dataset):
    cube = small_dataset.get("M_ha2edM", conditions=["measurement"])
    assert cube.device_codes == (2, 4, 6, 8, 10, 12, 14)
    assert {d.condition for d in cube.devices} == {Condition.MEASUREMENT}


def test_select_by_family_and_coupling(small_dataset):
    cube = small_dataset.get("M_ha2edM", families=["closed_earmold"])
    assert cube.device_codes == (1, 2)
    cube = small_dataset.get("M_ha2edM", couplings=["dome"])
    assert cube.device_codes == (9, 10, 11, 12, 13, 14)


def test_select_by_subject_reinsertion_and_frequency(small_dataset):
    cube = small_dataset.get("M_ha2edM").select(
        subjects=[2, 4], reinsertions=[1, 3], freq_range=(100.0, 1000.0)
    )
    assert tuple(cube.subjects) == (2, 4)
    assert tuple(cube.reinsertions) == (1, 3)
    assert cube.freq_hz.min() >= 100.0 and cube.freq_hz.max() <= 1000.0
    assert cube.values.shape == (cube.freq_hz.size, 14, 2, 2)


def test_select_does_not_mutate_original(cube):
    sliced = cube.select(subjects=[1, 2])
    assert sliced.shape != cube.shape
    assert cube.shape == (2049, 14, 14, 3)


def test_empty_selections_raise(small_dataset):
    with pytest.raises(DataSelectionError, match="no devices"):
        small_dataset.get("M_ha2edM", families=["closed_earmold"], couplings=["dome"])
    with pytest.raises(DataSelectionError, match="no subjects"):
        small_dataset.get("M_ha2edM", subjects=[999])
    with pytest.raises(DataSelectionError, match="no reinsertions"):
        small_dataset.get("M_ha2edM", reinsertions=[99])
    with pytest.raises(DataSelectionError, match="no frequencies"):
        small_dataset.get("M_ha2edM", freq_range=(30000.0, 40000.0))
    with pytest.raises(DataSelectionError, match="no devices"):
        small_dataset.get("M_ha2edM").select(device_codes=[])


# ---------------------------------------------------------------------------
# reinsertion aggregation
# ---------------------------------------------------------------------------
def test_mean_reinsertions(cube):
    mean = cube.mean_reinsertions()
    assert mean.shape == (2049, 14, 14, 1)
    assert tuple(mean.reinsertions) == (-1,)
    assert mean.metadata["aggregation"] == "mean_reinsertions"
    expected = np.nanmean(cube.masked, axis=3)
    np.testing.assert_allclose(mean.values[:, :, :, 0], expected)
    np.testing.assert_array_equal(mean.valid[:, :, :, 0], cube.valid.any(axis=3))


def test_std_reinsertions(cube):
    std = cube.std_reinsertions(ddof=1)
    assert std.shape == (2049, 14, 14, 1)
    masked = cube.masked
    expected = np.nanstd(masked.real, axis=3, ddof=1) + 1j * np.nanstd(
        masked.imag, axis=3, ddof=1
    )
    np.testing.assert_allclose(std.values[:, :, :, 0], expected, equal_nan=True)
    np.testing.assert_array_equal(std.valid[:, :, :, 0], cube.valid.sum(axis=3) > 1)
    assert std.metadata["ddof"] == 1


def test_subject_level_means(cube):
    means = cube.subject_level_means(reference=20e-6)
    assert means.shape == (2049, 14, 14)
    expected = np.nanmean(cube.level_array(reference=20e-6), axis=3)
    np.testing.assert_allclose(means, expected)


# ---------------------------------------------------------------------------
# tidy frames: ordering must be verified against direct array indexing
# ---------------------------------------------------------------------------
def test_to_dataframe_ordering(small_dataset, cube):
    selection = cube.select(device_codes=[2, 4], subjects=[3, 5], reinsertions=[1, 3])
    n_freq, n_dev, n_subj, n_re = selection.shape
    frame = selection.to_dataframe()
    assert len(frame) == n_freq * n_dev * n_subj * n_re
    assert list(frame.columns) == [
        "frequency_hz",
        "device_code",
        "device",
        "family",
        "family_label",
        "coupling",
        "condition",
        "subject",
        "reinsertion",
        "value",
        "valid",
    ]
    for frequency_index, device_index, subject_index, reinsertion_index in [
        (0, 0, 0, 0),
        (1, 1, 0, 1),
        (1234, 0, 1, 0),
        (n_freq - 1, 1, 1, 1),
        (17, 1, 1, 0),
    ]:
        expected_index = (
            (frequency_index * n_dev + device_index) * n_subj + subject_index
        ) * n_re + reinsertion_index
        row = frame.iloc[expected_index]
        assert row["frequency_hz"] == selection.freq_hz[frequency_index]
        assert row["device_code"] == selection.devices[device_index].code
        assert row["subject"] == selection.subjects[subject_index]
        assert row["reinsertion"] == selection.reinsertions[reinsertion_index]
        assert row["condition"] == selection.devices[device_index].condition.value
        np.testing.assert_equal(
            row["value"],
            selection.values[frequency_index, device_index, subject_index, reinsertion_index],
        )
        assert bool(row["valid"]) == bool(
            selection.valid[frequency_index, device_index, subject_index, reinsertion_index]
        )


def test_to_dataframe_valid_only(cube):
    full = cube.to_dataframe()
    valid_only = cube.to_dataframe(valid_only=True)
    assert len(valid_only) == int(cube.valid.sum())
    assert valid_only["valid"].all()
    assert len(full) > len(valid_only)
    # The invalid rows are exactly the structurally invalid / NaN sessions.
    assert len(full) - len(valid_only) == int((~cube.valid).sum())


def test_to_level_dataframe_explicit(cube):
    levels = cube.magnitude_db(reference=20e-6)
    frame = levels.to_dataframe()
    frame["level_db"] = frame["value"].astype(float)
    explicit = cube.to_level_dataframe(reference=20e-6)
    np.testing.assert_allclose(
        explicit["level_db"].to_numpy(), frame["level_db"].to_numpy(), equal_nan=True
    )
    # Spot check one row against the complex value.
    n_dev, n_subj, n_re = 14, 14, 3
    frequency_index, device_index, subject_index, reinsertion_index = (10, 3, 0, 1)
    index = ((frequency_index * n_dev + device_index) * n_subj + subject_index) * n_re + reinsertion_index
    value = cube.values[frequency_index, device_index, subject_index, reinsertion_index]
    assert explicit.loc[index, "level_db"] == pytest.approx(
        20 * np.log10(np.abs(value) / 20e-6)
    )


# ---------------------------------------------------------------------------
# level aggregations
# ---------------------------------------------------------------------------
def test_band_levels_power_consistency(small_dataset, cube, bands):
    selection = cube.select(freq_range=(0.0, 8000.0))
    reference = 20e-6
    frame = selection.band_levels(bands, reference=reference)
    assert not frame.empty
    assert {"band", "band_center_hz", "level_db", "valid", "subject", "reinsertion"}.issubset(
        frame.columns
    )
    power = np.abs(selection.masked) ** 2
    for band_label in ("63 Hz", "1000 Hz", "4000 Hz"):
        band = next(b for b in bands if b.label == band_label)
        mask = band.contains(selection.freq_hz)
        assert mask.any()
        mean_power = np.nanmean(power[mask], axis=0)
        expected_level = 10.0 * np.log10(mean_power / reference**2)
        expected_valid = selection.valid[mask].any(axis=0)
        rows = frame.loc[frame["band"] == band_label]
        for device_index, device in enumerate(selection.devices):
            for subject_index, subject in enumerate(selection.subjects):
                for reinsertion_index, reinsertion in enumerate(selection.reinsertions):
                    row = rows.loc[
                        (rows["device_code"] == device.code)
                        & (rows["subject"] == subject)
                        & (rows["reinsertion"] == reinsertion)
                    ].iloc[0]
                    assert bool(row["valid"]) == bool(
                        expected_valid[device_index, subject_index, reinsertion_index]
                    )
                    if expected_valid[device_index, subject_index, reinsertion_index]:
                        assert row["level_db"] == pytest.approx(
                            expected_level[device_index, subject_index, reinsertion_index]
                        )


def test_band_levels_requires_transfer_cube(small_dataset, bands):
    with pytest.raises(ValueError, match="transfer cube"):
        small_dataset.threshold().band_levels(bands)
    with pytest.raises(DataValidationError, match="No configured frequency band"):
        small_dataset.get("M_ha2edM").select(freq_range=(0.0, 30.0)).band_levels(bands)


def test_median_level_curve(cube):
    # Device code 4 (index 3) has no planted NaN session.
    selection = cube.select(device_codes=[4])
    levels = selection.level_cube(reference=20e-6).masked
    curve = selection.median_level_curve(reference=20e-6)
    assert len(curve) == selection.n_frequencies
    assert set(curve["device_code"]) == {4}
    expected = np.nanmedian(levels[:, 0], axis=(1, 2))
    np.testing.assert_allclose(curve["median_db"].to_numpy(), expected)
    for column in ("frequency_hz", "mean_db", "sd_db", "n_valid", "family", "condition"):
        assert column in curve.columns
    assert curve["n_valid"].max() == selection.n_subjects * selection.n_reinsertions


def test_level_cube_and_magnitude_db(cube):
    level = cube.magnitude_db(reference=20e-6)
    assert level.kind == "level_db"
    assert level.unit == "dB"
    assert level.valid is not cube.valid
    np.testing.assert_array_equal(level.valid, cube.valid)
    expected = 20 * np.log10(np.abs(cube.masked) / 20e-6)
    np.testing.assert_allclose(level.values, expected)
    assert level.level_cube() is level
    assert cube.level_cube() is not cube
    with pytest.raises(ValueError, match="requires a transfer cube"):
        level.magnitude_db()
    with pytest.raises(ValueError, match="requires a transfer cube"):
        level.phase_deg()


def test_phase_deg_cube(cube):
    phase = cube.phase_deg()
    assert phase.kind == "phase_deg"
    np.testing.assert_allclose(phase.values, np.degrees(np.angle(cube.masked)))


def test_with_name(cube):
    renamed = cube.with_name("custom")
    assert renamed.name == "custom"
    assert cube.name == "M_ha2edM"


# ---------------------------------------------------------------------------
# derived reference: in-situ free field
# ---------------------------------------------------------------------------
def test_free_field_reference(small_dataset):
    cube = small_dataset.free_field_reference()
    assert cube.shape == (2049, 1, N_SUBJECTS, N_REINSERTIONS)
    assert cube.devices == (DEVICE_FREE_FIELD,)
    raw = small_dataset.values("M_ls2edM")
    reference_indices = [0, 2, 4, 6, 8, 10, 12]
    expected = np.nanmedian(raw[:, reference_indices, :, :], axis=1)
    np.testing.assert_allclose(cube.values[:, 0], expected)
    expected_valid = np.isfinite(raw[:, reference_indices, :, :]).sum(axis=1) >= 5
    np.testing.assert_array_equal(cube.valid[:, 0], expected_valid)


def test_free_field_reference_per_device(small_dataset):
    cube = small_dataset.free_field_reference(per_device=True)
    assert cube.shape == (2049, 7, N_SUBJECTS, N_REINSERTIONS)
    assert cube.device_codes == (1, 3, 5, 7, 9, 11, 13)
    raw = small_dataset.values("M_ls2edM")
    np.testing.assert_allclose(cube.values, raw[:, [0, 2, 4, 6, 8, 10, 12], :, :])


def test_free_field_reference_subject_selection(small_dataset):
    cube = small_dataset.free_field_reference(subjects=[1, 2], reinsertions=[1])
    assert cube.shape == (2049, 1, 2, 1)
    assert tuple(cube.subjects) == (1, 2)


# ---------------------------------------------------------------------------
# invalid sessions / summary / describe
# ---------------------------------------------------------------------------
def test_invalid_sessions_table(small_dataset, small_nan_sessions):
    table = small_dataset.invalid_sessions("M_ha2edM")
    assert isinstance(table, pd.DataFrame)
    assert len(table) == len(small_nan_sessions["M_ha2edM"])
    row = table.iloc[0]
    device, subject, reinsertion = small_nan_sessions["M_ha2edM"][0]
    assert row["container"] == "M_ha2edM"
    assert row["device_code"] == small_dataset.devices[device].code
    assert row["subject"] == small_dataset.subjects[subject]
    assert row["reinsertion"] == small_dataset.reinsertions[reinsertion]
    assert bool(row["measured_nan"])
    assert row["structurally_valid"]
    threshold_table = small_dataset.invalid_sessions("M_thr_ha")
    assert threshold_table.empty
    reur_table = small_dataset.invalid_sessions(REUR_CONTAINER_KEY)
    assert reur_table.empty
    assert list(reur_table.columns) == [
        "container",
        "device_code",
        "device",
        "subject",
        "reinsertion",
        "reason",
    ]


def test_session_validity_summary(small_dataset):
    summary = small_dataset.session_validity_summary()
    assert len(summary) == 7
    counts = summary.set_index("container")["n_invalid_sessions"].to_dict()
    assert counts["M_ha2edM"] == 1
    assert counts["M_ha2edR"] == 1
    assert counts["M_ha2haf"] == 0
    assert counts["M_ls2edM"] == 0
    assert counts["M_ls2edR"] == 0
    assert counts["M_thr_ha"] == 0
    assert counts["M_REUR"] == 0
    sessions = summary.set_index("container")["n_sessions"].to_dict()
    assert sessions["M_ha2edM"] == 14 * 14 * 3
    assert sessions["M_REUR"] == 14
    assert summary["invalid_fraction"].between(0.0, 1.0).all()


def test_summary(small_dataset):
    summary = small_dataset.summary()
    assert summary["n_frequencies"] == 2049
    assert summary["frequency_range_hz"] == [0.0, 22050.0]
    assert summary["frequency_resolution_hz"] == pytest.approx(22050.0 / 2048.0)
    assert summary["threshold_frequencies_hz"] == [125, 250, 500, 750, 1000, 2000]
    assert summary["n_devices"] == 14
    assert summary["n_subjects"] == 14
    assert summary["n_reinsertions"] == 3
    assert summary["containers"] == list(CONTAINER_ORDER)
    assert len(summary["invalid_sessions"]) == 7
    assert summary["configuration"]["invalid_policy"] == "exclude"
    assert summary["file"]["mat_format"] == "v5"


def test_describe(small_dataset):
    text = small_dataset.describe()
    assert "AcousticBench dataset" in text
    for key in CONTAINER_ORDER:
        assert key in text
    assert "22050" in text


# ---------------------------------------------------------------------------
# TransferCube defensive validation
# ---------------------------------------------------------------------------
def test_transfer_cube_validation(small_dataset):
    base = small_dataset.reur()
    with pytest.raises(ValueError, match="4-D"):
        replace(base, values=base.values[..., 0])
    with pytest.raises(ValueError, match="valid mask"):
        replace(base, valid=base.valid[..., :-1])
    with pytest.raises(ValueError, match="frequency axis"):
        replace(base, freq_hz=base.freq_hz[:-1])
    with pytest.raises(ValueError, match="device axis"):
        replace(base, devices=())
    with pytest.raises(ValueError, match="subject axis"):
        replace(base, subjects=base.subjects[:-1])
    with pytest.raises(ValueError, match="reinsertion axis"):
        replace(base, reinsertions=np.array([1, 2]))
    with pytest.raises(ValueError, match="unknown cube kind"):
        replace(base, kind="banana")


# ---------------------------------------------------------------------------
# construction from file
# ---------------------------------------------------------------------------
def test_load_dataset_from_file(config, small_mat_file):
    dataset = load_dataset(small_mat_file, config=config, compute_hash=False)
    assert isinstance(dataset, AcousticDataset)
    assert dataset.frequency_hz.size == 2049
    assert dataset.info.sha256 == ""


def test_acoustic_dataset_from_file_classmethod(config, small_mat_file):
    dataset = AcousticDataset.from_file(small_mat_file, config=config, compute_hash=True)
    assert len(dataset.info.sha256) == 64


def test_load_dataset_missing_file_raises(config, tmp_path):
    with pytest.raises(DataValidationError, match="not found"):
        load_dataset(tmp_path / "missing.mat", config=config)


def test_dataset_validation_rejects_bad_shapes(config, small_mat_file):
    from acousticbench.io.mat_loader import load_mat

    raw = load_mat(small_mat_file, compute_hash=False)
    bad_variables = dict(raw.variables)
    bad_variables["M_REUR"] = bad_variables["M_REUR"][:, : 13]
    bad_raw = replace(raw, variables=bad_variables)
    with pytest.raises(DataValidationError, match="M_REUR"):
        AcousticDataset(bad_raw, config=config)


# ---------------------------------------------------------------------------
# real-data checks
# ---------------------------------------------------------------------------
@pytest.mark.requires_data
def test_real_dataset_shapes_and_axes(dataset):
    assert dataset.frequency_hz.size == 2049
    assert dataset.frequency_hz[0] == 0.0
    assert dataset.frequency_hz[-1] == pytest.approx(22050.0)
    np.testing.assert_allclose(np.diff(dataset.frequency_hz), 22050.0 / 2048.0)
    np.testing.assert_allclose(dataset.threshold_frequency_hz, [125, 250, 500, 750, 1000, 2000])
    assert dataset.subjects.size == 14
    assert dataset.reinsertions.size == 3
    assert len(dataset.devices) == 14
    for key in TRANSFER_CONTAINER_KEYS:
        assert dataset.values(key).shape == (2049, 14, 14, 3)
    assert dataset.values(THRESHOLD_CONTAINER_KEY).shape == (6, 14, 14, 3)
    assert dataset.values(REUR_CONTAINER_KEY).shape == (2049, 14)


@pytest.mark.requires_data
def test_real_dataset_invalid_sessions(dataset):
    summary = dataset.session_validity_summary().set_index("container")
    for key in TRANSFER_CONTAINER_KEYS:
        assert int(summary.loc[key, "n_invalid_sessions"]) == 18
        assert int(summary.loc[key, "n_sessions"]) == 588
    assert int(summary.loc[THRESHOLD_CONTAINER_KEY, "n_invalid_sessions"]) == 19
    assert int(summary.loc[REUR_CONTAINER_KEY, "n_invalid_sessions"]) == 0
    transfer_table = dataset.invalid_sessions("M_ha2edM")
    assert len(transfer_table) == 18
    assert transfer_table["device_code"].between(1, 14).all()
    assert set(dataset.structural_mask("M_ha2edM")) == {False, True}


@pytest.mark.requires_data
def test_real_dataset_valid_fractions(dataset):
    fractions = {key: dataset.get(key).valid_fraction for key in CONTAINER_ORDER}
    assert fractions["M_ha2edM"] == pytest.approx(0.4847, abs=5e-4)
    assert fractions["M_ha2edR"] == pytest.approx(0.5408, abs=5e-4)
    assert fractions["M_ha2haf"] > 0.96
    assert fractions["M_thr_ha"] > 0.96
    assert fractions[REUR_CONTAINER_KEY] == pytest.approx(1.0)


@pytest.mark.requires_data
def test_real_audit(dataset):
    audit = dataset.audit()
    assert audit.n_errors == 0
    assert audit.passed is True
    assert len(audit.findings) == 17
    codes = {finding.code for finding in audit.findings}
    for expected_code in (
        "nan_session_consistency",
        "threshold_invalid_sessions",
        "frequency_axis",
        "threshold_axis",
        "structural_mpt_loose_in_reference",
        "structural_rpt_missing_for_domes",
        "units_hha_db_spl",
        "units_cross_probe_agreement",
        "units_reoig_sign",
        "expected_ptpe_direction",
        "invalid_values_never_imputed",
    ):
        assert expected_code in codes
    statuses = {finding.status for finding in audit.findings}
    assert "WARN" not in statuses
    checks = audit.checks_frame()
    assert len(checks) == 17
    payload = audit.to_dict()
    assert payload["summary"]["n_errors"] == 0
    assert payload["frequency_axis"]["n_bins"] == 2049
    assert payload["threshold_axis"]["frequencies_hz"] == [125, 250, 500, 750, 1000, 2000]
    assert payload["provenance"]["dataset_doi"] == "10.5281/zenodo.20023285"
    assert "AcousticBench data audit" in audit.to_markdown()


@pytest.mark.requires_data
def test_real_dataset_describe_and_summary(dataset):
    text = dataset.describe()
    assert "AcousticBench dataset" in text
    assert "2049" in text
    summary = dataset.summary()
    assert summary["n_frequencies"] == 2049
    assert summary["file"]["mat_format"] == "v5"
    assert summary["invalid_sessions"][0]["container"] == "M_ha2edM"
