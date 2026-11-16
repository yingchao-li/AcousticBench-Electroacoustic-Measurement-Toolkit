"""Unit tests for :mod:`acousticbench.measurements`.

Mechanics (formulas, units, structural-validity handling, PTPE sign
conventions, threshold tables) are tested on the synthetic schema-valid
dataset, so the data-free CI subset still exercises the measurement layer.
The physical regression-style checks on the real measurements are marked
``requires_data``.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from acousticbench.data.dataset import AcousticDataset
from acousticbench.exceptions import DataValidationError, MeasurementError
from acousticbench.measurements.ptpe import (
    family_axis,
    probe_bias_band_levels,
    probe_bias_db,
    ptpe_hha_band_levels,
    ptpe_hha_db,
    ptpe_reoig_band_levels,
    ptpe_reoig_db,
    ptpe_summary,
    ptpe_threshold_db,
    threshold_ptpe,
)
from acousticbench.measurements.threshold import (
    audiogram_summary,
    threshold_curve,
    threshold_difference_table,
    threshold_table,
)
from acousticbench.measurements.transfer import (
    eardrum_pressure,
    feedback_path_db_pa_per_v,
    feedback_path_db_spl,
    hha_band_levels,
    hha_db_pa_per_v,
    hha_db_spl,
    hha_frequency_response,
    loudspeaker_response,
    reog_band_levels,
    reog_db,
    reoig_band_levels,
    reoig_db,
    reug_band_levels,
    reug_db,
    structurally_valid_codes,
    threshold_dbv,
)
from acousticbench.types import P_REF_PA, U_HA_DRIVE_V, Condition, Coupling, Probe, Source

_DB_SPL_MINUS_PA_PER_V = 20 * math.log10(U_HA_DRIVE_V / P_REF_PA)  # 54.9595…
_PA_PER_V_MINUS_RE_PA = 20 * math.log10(1.0 / U_HA_DRIVE_V)  # 39.0103…


def _finite(values: np.ndarray) -> np.ndarray:
    return np.asarray(values)[np.isfinite(values)]


# ---------------------------------------------------------------------------
# structural validity and error handling
# ---------------------------------------------------------------------------
def test_structurally_valid_codes(small_dataset):
    assert structurally_valid_codes(small_dataset, "M_ha2edM") == (2, 4, 6, 8, 10, 12, 14)
    assert structurally_valid_codes(small_dataset, "M_ha2edR") == (1, 2, 3, 4, 5, 6, 7, 8)
    assert structurally_valid_codes(small_dataset, "M_ha2haf") == tuple(range(1, 15))
    assert structurally_valid_codes(small_dataset, "M_ls2edM") == (2, 4, 6, 8, 10, 12, 14)
    assert structurally_valid_codes(small_dataset, "M_ls2edR") == (1, 2, 3, 4, 5, 6, 7, 8)


def test_eardrum_pressure_rejects_measurement_probe_in_reference_condition(small_dataset):
    with pytest.raises(MeasurementError, match="not a physically meaningful eardrum pressure"):
        eardrum_pressure(
            small_dataset,
            source=Source.HEARING_AID_DRIVER,
            probe=Probe.MEASUREMENT,
            condition=Condition.REFERENCE,
        )
    with pytest.raises(MeasurementError):
        loudspeaker_response(
            small_dataset, probe=Probe.MEASUREMENT, condition=Condition.REFERENCE
        )


def test_eardrum_pressure_rejects_reference_probe_for_domes(small_dataset):
    with pytest.raises(MeasurementError, match="structurally invalid"):
        eardrum_pressure(
            small_dataset,
            source=Source.HEARING_AID_DRIVER,
            probe=Probe.REFERENCE,
            condition=Condition.MEASUREMENT,
            couplings=["dome"],
        )
    with pytest.raises(MeasurementError, match="structurally invalid"):
        eardrum_pressure(
            small_dataset,
            source=Source.HEARING_AID_DRIVER,
            probe=Probe.REFERENCE,
            condition=Condition.MEASUREMENT,
            families=["open_dome"],
        )


def test_eardrum_pressure_rejects_invalid_enums_and_codes(small_dataset):
    with pytest.raises(MeasurementError, match="Invalid source"):
        eardrum_pressure(
            small_dataset, source="banana", probe="measurement", condition="measurement"
        )
    with pytest.raises(MeasurementError, match="Invalid probe"):
        eardrum_pressure(
            small_dataset, source="hearing_aid_driver", probe="banana", condition="measurement"
        )
    with pytest.raises(MeasurementError, match="Invalid condition"):
        eardrum_pressure(
            small_dataset, source="hearing_aid_driver", probe="measurement", condition="banana"
        )
    with pytest.raises(MeasurementError, match="structurally invalid"):
        eardrum_pressure(
            small_dataset,
            source=Source.HEARING_AID_DRIVER,
            probe=Probe.MEASUREMENT,
            condition=Condition.MEASUREMENT,
            device_codes=[1, 7],
        )
    with pytest.raises(MeasurementError, match="Invalid coupling"):
        eardrum_pressure(
            small_dataset,
            source=Source.HEARING_AID_DRIVER,
            probe=Probe.MEASUREMENT,
            condition=Condition.MEASUREMENT,
            couplings=["banana"],
        )


def test_eardrum_pressure_returns_masked_pressure(small_dataset):
    cube = eardrum_pressure(
        small_dataset,
        source=Source.HEARING_AID_DRIVER,
        probe=Probe.MEASUREMENT,
        condition=Condition.MEASUREMENT,
    )
    raw = small_dataset.get("M_ha2edM", conditions=[Condition.MEASUREMENT], device_codes=[2, 4, 6, 8, 10, 12, 14])
    assert cube.device_codes == (2, 4, 6, 8, 10, 12, 14)
    np.testing.assert_array_equal(cube.values, raw.values)
    np.testing.assert_array_equal(cube.valid, raw.valid)
    assert cube.name.startswith("M_ha2edM")


def test_eardrum_pressure_selection(small_dataset):
    cube = eardrum_pressure(
        small_dataset,
        source=Source.LOUDSPEAKER,
        probe=Probe.MEASUREMENT,
        condition=Condition.MEASUREMENT,
        subjects=[1, 2],
        reinsertions=[1],
        families=["closed_earmold"],
    )
    assert cube.device_codes == (2,)
    assert tuple(cube.subjects) == (1, 2)
    assert tuple(cube.reinsertions) == (1,)


# ---------------------------------------------------------------------------
# Hha levels and units
# ---------------------------------------------------------------------------
def test_hha_db_spl_formula(small_dataset):
    cube = hha_db_spl(small_dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT)
    raw = small_dataset.get(
        "M_ha2edM", conditions=[Condition.MEASUREMENT], device_codes=[2, 4, 6, 8, 10, 12, 14]
    )
    expected = 20 * np.log10(np.abs(raw.masked) / P_REF_PA)
    np.testing.assert_allclose(cube.values, expected, equal_nan=True)
    assert cube.unit == "dB"
    assert "dB SPL" in cube.unit_label
    assert "Hha" in cube.name


def test_hha_db_spl_plausible_range_real(dataset):
    cube = hha_db_spl(dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT)
    band = cube.select(freq_range=(500.0, 4000.0))
    levels = _finite(band.values)
    assert levels.size > 0
    assert 40.0 < np.nanmedian(levels) < 110.0


def test_hha_dB_pa_per_v_offsets(small_dataset):
    spl = hha_db_spl(small_dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT)
    pa_per_v = hha_db_pa_per_v(
        small_dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT
    )
    both = spl.valid & pa_per_v.valid
    difference = spl.values[both] - pa_per_v.values[both]
    np.testing.assert_allclose(difference, _DB_SPL_MINUS_PA_PER_V, atol=1e-9)
    # dB re Pa/V relative to a plain dB re 1 Pa level differs by 20log10(1/0.0112).
    raw = small_dataset.get(
        "M_ha2edM", conditions=[Condition.MEASUREMENT], device_codes=[2, 4, 6, 8, 10, 12, 14]
    )
    re_pa = 20 * np.log10(np.abs(raw.masked))
    np.testing.assert_allclose(
        pa_per_v.values[both] - re_pa[both], _PA_PER_V_MINUS_RE_PA, atol=1e-9
    )
    assert pa_per_v.unit_label == "dB re 1 Pa/V"


def test_hha_frequency_response(small_dataset):
    frame = hha_frequency_response(
        small_dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT
    )
    expected = hha_db_spl(
        small_dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT
    ).median_level_curve()
    pd.testing.assert_frame_equal(frame, expected)


def test_hha_band_levels(small_dataset, bands):
    frame = hha_band_levels(
        small_dataset, bands, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT
    )
    assert not frame.empty
    assert frame["quantity"].eq("Hha").all()
    assert frame["unit"].eq("dB SPL @ 11.2 mV").all()
    assert {"band", "level_db", "valid"}.issubset(frame.columns)


# ---------------------------------------------------------------------------
# feedback path
# ---------------------------------------------------------------------------
def test_feedback_path(small_dataset):
    spl = feedback_path_db_spl(small_dataset, condition=Condition.MEASUREMENT)
    raw = small_dataset.get("M_ha2haf", conditions=[Condition.MEASUREMENT])
    np.testing.assert_allclose(
        spl.values, 20 * np.log10(np.abs(raw.masked) / P_REF_PA), equal_nan=True
    )
    assert spl.valid.all()
    pa_per_v = feedback_path_db_pa_per_v(small_dataset, condition=Condition.MEASUREMENT)
    difference = spl.values[spl.valid] - pa_per_v.values[spl.valid]
    np.testing.assert_allclose(difference, _DB_SPL_MINUS_PA_PER_V, atol=1e-9)


def test_feedback_path_real_data(dataset):
    spl = feedback_path_db_spl(dataset, condition=Condition.MEASUREMENT)
    finite = _finite(spl.values)
    assert finite.size / spl.values.size > 0.9
    assert 10.0 < np.nanmedian(finite) < 90.0


# ---------------------------------------------------------------------------
# real-ear gains
# ---------------------------------------------------------------------------
def test_reoig_consistency_with_direct_ratio(small_dataset):
    occluded = loudspeaker_response(
        small_dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT
    )
    reur = small_dataset.reur()
    cube = reoig_db(
        small_dataset, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT
    )
    assert cube.shape == occluded.shape
    assert cube.kind == "level_db"
    assert cube.unit == "dB"
    assert "REOIG" in cube.name
    # REOIG = 20log10|p_occluded| - 20log10|p_open| evaluated directly.
    open_values = np.broadcast_to(
        np.abs(reur.masked)[:, :1, :, :], occluded.values.shape
    )
    expected = 20 * np.log10(np.abs(occluded.masked)) - 20 * np.log10(open_values)
    np.testing.assert_allclose(cube.values, expected, equal_nan=True)
    np.testing.assert_array_equal(cube.valid, occluded.valid & reur.valid[:, :1, :, :])


def test_reoig_reference_probe_variant(small_dataset):
    cube = reoig_db(
        small_dataset, condition=Condition.REFERENCE, probe=Probe.REFERENCE
    )
    assert cube.device_codes == (1, 3, 5, 7)
    assert cube.metadata["probe"] == "reference"


def test_reoig_real_data_closed_earmold(dataset):
    curve = reoig_db(
        dataset, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT,
        families=["closed_earmold"],
    ).median_level_curve()
    row = curve.loc[np.argmin(np.abs(curve["frequency_hz"] - 1000.0))]
    assert -12.0 < row["median_db"] < -9.0
    open_curve = reoig_db(
        dataset, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT,
        families=["open_dome"],
    ).median_level_curve()
    open_row = open_curve.loc[np.argmin(np.abs(open_curve["frequency_hz"] - 1000.0))]
    assert abs(open_row["median_db"]) < 6.0


def test_reog_db_re_free_field(small_dataset):
    occluded = loudspeaker_response(
        small_dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT
    )
    free = small_dataset.free_field_reference()
    cube = reog_db(small_dataset, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT)
    expected = 20 * np.log10(np.abs(occluded.masked)) - 20 * np.log10(
        np.abs(free.masked)
    )
    np.testing.assert_allclose(cube.values, expected, equal_nan=True)
    assert cube.valid.sum() > 0
    assert "REOG" in cube.name


def test_reug_db(small_dataset):
    reur = small_dataset.reur()
    free = small_dataset.free_field_reference()
    free_median = np.nanmedian(np.abs(free.masked), axis=3, keepdims=True)
    cube = reug_db(small_dataset)
    expected = 20 * np.log10(np.abs(reur.masked)) - 20 * np.log10(free_median)
    np.testing.assert_allclose(cube.values, expected, equal_nan=True)
    assert tuple(cube.reinsertions) == (-1,)
    mean_cube = reug_db(small_dataset, free_field_aggregation="mean")
    assert not np.allclose(mean_cube.values[cube.valid], cube.values[cube.valid])
    with pytest.raises(MeasurementError, match="free_field_aggregation"):
        reug_db(small_dataset, free_field_aggregation="banana")


def test_reug_real_data_resonance(dataset):
    cube = reug_db(dataset)
    frame = cube.to_dataframe(valid_only=True)
    band = frame.loc[(frame["frequency_hz"] >= 2000.0) & (frame["frequency_hz"] <= 4000.0)]
    assert np.nanmedian(band["value"]) > 5.0


def test_band_level_conveniences(small_dataset, bands):
    reoig_bands = reoig_band_levels(
        small_dataset, bands, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT
    )
    assert {"reoig_db", "valid", "band", "subject"}.issubset(reoig_bands.columns)
    assert not reoig_bands.empty
    reog_bands = reog_band_levels(
        small_dataset, bands, condition=Condition.MEASUREMENT, probe=Probe.MEASUREMENT
    )
    assert {"reog_db", "valid", "reinsertion"}.issubset(reog_bands.columns)
    reug_bands = reug_band_levels(small_dataset, bands)
    assert {"reug_db", "valid"}.issubset(reug_bands.columns)
    assert (reug_bands["reinsertion"] == -1).all()


def test_difference_frames_error(small_dataset):
    # A band set outside the cube's frequency range yields no rows at all.
    with pytest.raises(DataValidationError):
        reoig_band_levels(
            small_dataset,
            bands=family_axis_bands(),
            condition=Condition.REFERENCE,
            probe=Probe.REFERENCE,
            subjects=[1],
        )


def family_axis_bands():
    from acousticbench.stats.bands import custom_bands

    return custom_bands([30000.0, 40000.0])


# ---------------------------------------------------------------------------
# thresholds
# ---------------------------------------------------------------------------
def test_threshold_dbv(small_dataset):
    cube = threshold_dbv(small_dataset)
    np.testing.assert_array_equal(cube.values, small_dataset.threshold().values)
    assert cube.kind == "threshold_dbv"


def test_threshold_tables(small_dataset):
    table = threshold_table(small_dataset)
    assert len(table) == 6 * 14 * 14 * 3  # all finite in the synthetic fixture
    assert {"threshold_dbv", "valid", "family", "condition"}.issubset(table.columns)
    assert table["valid"].all()

    curve = threshold_curve(small_dataset)
    assert len(curve) == 7 * 2 * 6
    assert {"median_dbv", "mean_dbv", "sd_dbv", "n_subjects"}.issubset(curve.columns)
    assert (curve["n_subjects"] == 14).all()

    summary = audiogram_summary(small_dataset)
    assert len(summary) == 7 * 2 * 6
    assert "n" in summary.columns

    difference = threshold_difference_table(small_dataset)
    assert len(difference) == 7 * 6 * 14 * 3
    assert {"family", "delta_t_db", "t_reference_dbv", "t_measurement_dbv"}.issubset(
        difference.columns
    )
    # t_ref - t_meas as defined (negative for a probe-insertion output drop).
    np.testing.assert_allclose(
        difference["delta_t_db"],
        difference["t_reference_dbv"] - difference["t_measurement_dbv"],
    )
    mapping = difference.set_index("family")["measurement_device_code"].to_dict()
    assert mapping == {
        "closed_earmold": 2,
        "vented_earmold": 4,
        "nugget_earmold": 6,
        "silicone_earmold": 8,
        "open_dome": 10,
        "tulip_dome": 12,
        "power_dome": 14,
    }


def test_threshold_table_selection(small_dataset):
    table = threshold_table(small_dataset, conditions=["measurement"], families=["open_dome"])
    assert table["condition"].eq("measurement").all()
    assert table["family"].eq("open_dome").all()


def test_threshold_real_data(dataset):
    table = threshold_table(dataset)
    assert not table.empty
    assert table["threshold_dbv"].between(-140.0, 0.0).all()
    # 1 dB quantisation.
    residuals = np.abs(table["threshold_dbv"] - np.round(table["threshold_dbv"]))
    assert residuals.max() <= 1e-6
    curve = threshold_curve(dataset)
    assert len(curve) == 7 * 2 * 6
    difference = threshold_difference_table(dataset)
    assert len(difference) > 0


# ---------------------------------------------------------------------------
# PTPE and probe bias
# ---------------------------------------------------------------------------
def test_family_axis():
    axis = family_axis()
    assert len(axis) == 7
    assert tuple(d.code for d in axis) == tuple(range(101, 108))
    assert [d.family for d in axis] == [
        "closed_earmold",
        "vented_earmold",
        "nugget_earmold",
        "silicone_earmold",
        "open_dome",
        "tulip_dome",
        "power_dome",
    ]
    assert all(d.condition is None for d in axis)
    subset = family_axis(["closed_earmold"], suffix=" · ΔHha")
    assert len(subset) == 1
    assert subset[0].label.endswith("ΔHha")


def test_probe_bias_db(small_dataset):
    cube = probe_bias_db(small_dataset, condition=Condition.MEASUREMENT)
    assert cube.device_codes == (2, 4, 6, 8)
    mpt = hha_db_spl(small_dataset, probe=Probe.MEASUREMENT, condition=Condition.MEASUREMENT)
    rpt = hha_db_spl(small_dataset, probe=Probe.REFERENCE, condition=Condition.MEASUREMENT)
    mpt = mpt.select(device_codes=cube.device_codes)
    rpt = rpt.select(device_codes=cube.device_codes)
    np.testing.assert_allclose(cube.values, mpt.values - rpt.values, equal_nan=True)
    assert cube.unit_label == "dB (MPT − RPT)"


def test_probe_bias_band_levels(small_dataset, bands):
    frame = probe_bias_band_levels(small_dataset, bands, condition=Condition.MEASUREMENT)
    assert {"bias_db", "valid", "family", "band"}.issubset(frame.columns)
    assert not frame.empty


def test_probe_bias_real_data(dataset):
    cube = probe_bias_db(dataset, condition=Condition.MEASUREMENT)
    band = cube.select(freq_range=(500.0, 4000.0))
    values = np.abs(_finite(band.values))
    assert values.size > 0
    assert np.nanmedian(values) < 3.0


def test_ptpe_hha_db(small_dataset):
    cube = ptpe_hha_db(small_dataset)
    assert cube.shape == (2049, 4, 14, 3)
    assert cube.device_codes == (101, 102, 103, 104)
    assert {d.family for d in cube.devices} == {
        "closed_earmold",
        "vented_earmold",
        "nugget_earmold",
        "silicone_earmold",
    }
    measurement = hha_db_spl(
        small_dataset, probe=Probe.REFERENCE, condition=Condition.MEASUREMENT
    )
    reference = hha_db_spl(
        small_dataset, probe=Probe.REFERENCE, condition=Condition.REFERENCE
    )
    np.testing.assert_allclose(cube.values, measurement.values - reference.values, equal_nan=True)
    np.testing.assert_array_equal(cube.valid, measurement.valid & reference.valid)


def test_ptpe_reoig_db(small_dataset):
    cube = ptpe_reoig_db(small_dataset)
    assert cube.shape == (2049, 4, 14, 3)
    measurement = reoig_db(
        small_dataset, condition=Condition.MEASUREMENT, probe=Probe.REFERENCE
    )
    reference = reoig_db(
        small_dataset, condition=Condition.REFERENCE, probe=Probe.REFERENCE
    )
    np.testing.assert_allclose(cube.values, measurement.values - reference.values, equal_nan=True)
    assert "REOIG" in cube.name


def test_ptpe_threshold_db(small_dataset):
    cube = ptpe_threshold_db(small_dataset)
    assert cube.shape == (6, 7, 14, 3)
    assert cube.kind == "level_db"
    assert tuple(cube.freq_hz) == (125.0, 250.0, 500.0, 750.0, 1000.0, 2000.0)
    threshold = small_dataset.threshold()
    reference = threshold.select(device_codes=[1, 3, 5, 7, 9, 11, 13]).values
    measurement = threshold.select(device_codes=[2, 4, 6, 8, 10, 12, 14]).values
    np.testing.assert_allclose(cube.values, reference - measurement)
    # In the synthetic fixture the measurement-condition threshold is 0.5 dB higher.
    assert np.nanmedian(cube.values) == pytest.approx(-0.5)

    frame = threshold_ptpe(small_dataset)
    assert {"delta_t_db", "threshold_frequency_hz", "device_code"}.issubset(frame.columns)
    assert len(frame) == 6 * 7 * 14 * 3


def test_ptpe_band_frames(small_dataset, bands):
    hha = ptpe_hha_band_levels(small_dataset, bands)
    assert {"ptpe_db", "valid", "family", "band"}.issubset(hha.columns)
    assert not hha.empty
    reoig = ptpe_reoig_band_levels(small_dataset, bands)
    assert {"ptpe_db", "valid", "family", "band"}.issubset(reoig.columns)
    assert not reoig.empty


def test_ptpe_summary(small_dataset, bands):
    summary = ptpe_summary(small_dataset, bands)
    assert isinstance(summary, pd.DataFrame)
    assert set(summary["metric"]) == {"delta_hha", "delta_reoig", "delta_threshold"}
    assert {"family", "band", "band_center_hz", "value_db", "n_subjects"}.issubset(
        summary.columns
    )
    delta_threshold = summary.loc[summary["metric"] == "delta_threshold"]
    assert len(delta_threshold) == 7
    assert set(delta_threshold["band"]) == {"125 Hz"}
    assert delta_threshold["n_subjects"].eq(14).all()


# ---------------------------------------------------------------------------
# real-data PTPE sign conventions (regression-style)
# ---------------------------------------------------------------------------
@pytest.mark.requires_data
def test_ptpe_hha_low_frequency_negative_real(dataset, bands):
    frame = ptpe_hha_band_levels(dataset, bands)
    for family in ("nugget_earmold",):
        for center in (63.0, 125.0):
            subset = frame.loc[
                (frame["family"] == family)
                & (frame["band_center_hz"] == center)
                & frame["valid"]
            ]
            assert not subset.empty
            median = float(np.nanmedian(subset["ptpe_db"]))
            assert median < -3.0, (family, center, median)
    summary = ptpe_summary(dataset, bands)
    nugget_63 = summary.loc[
        (summary["metric"] == "delta_hha")
        & (summary["family"] == "nugget_earmold")
        & (summary["band_center_hz"] == 63.0)
    ]
    assert len(nugget_63) == 1
    assert -13.0 < float(nugget_63["value_db"].iloc[0]) < -10.0


@pytest.mark.requires_data
def test_ptpe_reoig_positive_real(dataset, bands):
    frame = ptpe_reoig_band_levels(dataset, bands)
    for family in ("closed_earmold", "nugget_earmold"):
        subset = frame.loc[
            (frame["family"] == family)
            & (frame["band_center_hz"] == 1000.0)
            & frame["valid"]
        ]
        assert not subset.empty
        assert float(np.nanmedian(subset["ptpe_db"])) > 0.5, family


@pytest.mark.requires_data
def test_ptpe_threshold_negative_real(dataset):
    cube = ptpe_threshold_db(dataset)
    index = int(np.argmin(np.abs(cube.freq_hz - 125.0)))
    values = cube.masked[index]
    families = np.array([device.family for device in cube.devices])
    for family in ("closed_earmold", "nugget_earmold", "power_dome"):
        mask = families == family
        assert np.isfinite(values[mask]).any()
        median = float(np.nanmedian(values[mask]))
        assert median < -1.0, (family, median)
