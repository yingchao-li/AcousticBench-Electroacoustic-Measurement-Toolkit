"""Unit tests for :mod:`acousticbench.types`, :mod:`acousticbench.data.units` and
:mod:`acousticbench.data.validity` (domain metadata, unit conversions and the
structural/measured validity rules).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from acousticbench.data.units import (
    dB_SPL_OFFSET,
    db_to_amplitude,
    db_to_pa,
    magnitude,
    magnitude_db,
    pa_to_db_pa_per_v,
    pa_to_db_spl,
    phase_deg,
    phase_rad,
    threshold_dbv_to_voltage,
)
from acousticbench.data.validity import (
    build_valid_mask,
    combined_valid_mask,
    finite_mask,
    invalid_reasons_table,
    invalid_sessions,
    structural_validity,
    structural_validity_table,
)
from acousticbench.exceptions import UnitError
from acousticbench.types import (
    ALL_DEVICES,
    CONTAINER_ORDER,
    CONTAINERS,
    DB_SPL_OFFSET_FROM_PA,
    DEVICE_BY_CODE,
    DEVICE_FREE_FIELD,
    DEVICE_OPEN_EAR,
    DEVICES,
    DOME_DEVICE_CODES,
    EARMOLD_DEVICE_CODES,
    FAMILIES,
    FREQUENCY_RESOLUTION_HZ,
    MEASUREMENT_DEVICE_CODES,
    N_FREQUENCIES,
    N_REINSERTIONS,
    N_SUBJECTS,
    N_THRESHOLD_FREQUENCIES,
    NYQUIST_HZ,
    P_REF_PA,
    REFERENCE_DEVICE_CODES,
    REUR_CONTAINER_KEY,
    THRESHOLD_CONTAINER_KEY,
    TRANSFER_CONTAINER_KEYS,
    U_HA_DRIVE_V,
    Condition,
    Coupling,
    Probe,
    Quantity,
    Source,
    device,
    devices_for,
    family_devices,
)


# ---------------------------------------------------------------------------
# device registry
# ---------------------------------------------------------------------------
def test_fourteen_device_codes():
    assert len(DEVICES) == 14
    assert tuple(d.code for d in DEVICES) == tuple(range(1, 15))


def test_odd_codes_are_reference_even_codes_measurement():
    for spec in DEVICES:
        expected = Condition.REFERENCE if spec.code % 2 == 1 else Condition.MEASUREMENT
        assert spec.condition is expected
        assert spec.label.endswith(expected.label)
        assert spec.short_label.endswith(expected.short)


def test_family_layout():
    # 4 earmold families and 3 dome families, two codes each.
    families = list(dict.fromkeys(d.family for d in DEVICES))
    assert families == [
        "closed_earmold",
        "vented_earmold",
        "nugget_earmold",
        "silicone_earmold",
        "open_dome",
        "tulip_dome",
        "power_dome",
    ]
    assert len(FAMILIES) == 7
    for family, label, coupling in FAMILIES:
        codes = [d for d in DEVICES if d.family == family]
        assert len(codes) == 2
        assert {c.coupling for c in codes} == {coupling}
        assert {c.family_label for c in codes} == {label}
        assert coupling is (Coupling.EARMOLD if family.endswith("earmold") else Coupling.DOME)


def test_device_code_groups():
    assert EARMOLD_DEVICE_CODES == (1, 2, 3, 4, 5, 6, 7, 8)
    assert DOME_DEVICE_CODES == (9, 10, 11, 12, 13, 14)
    assert REFERENCE_DEVICE_CODES == (1, 3, 5, 7, 9, 11, 13)
    assert MEASUREMENT_DEVICE_CODES == (2, 4, 6, 8, 10, 12, 14)


def test_device_spec_properties():
    closed = device(2)
    assert closed.is_earmold and not closed.is_dome
    assert closed.condition_label == "Measurement"
    assert device(1).condition_label == "Reference"
    assert DEVICE_OPEN_EAR.condition_label == "—"
    assert DEVICE_OPEN_EAR.coupling is Coupling.OPEN
    assert not DEVICE_OPEN_EAR.is_earmold
    assert not DEVICE_OPEN_EAR.is_dome


def test_device_lookup():
    assert device(1).family == "closed_earmold"
    assert device(14).family == "power_dome"
    assert device(0) is DEVICE_OPEN_EAR
    assert device(-1) is DEVICE_FREE_FIELD
    assert len(ALL_DEVICES) == 16
    assert DEVICE_BY_CODE[7] is device(7)
    with pytest.raises(KeyError, match="Unknown device code"):
        device(99)


def test_devices_for_filters():
    assert devices_for(conditions=["measurement"]) == tuple(
        d for d in DEVICES if d.condition is Condition.MEASUREMENT
    )
    assert devices_for(families=["closed_earmold"]) == (device(1), device(2))
    assert devices_for(couplings=["dome"]) == tuple(d for d in DEVICES if d.is_dome)
    assert devices_for(codes=[1, 3, 5]) == (device(1), device(3), device(5))
    assert devices_for(conditions=["reference"], families=["closed_earmold"]) == (device(1),)


def test_family_devices():
    assert [d.code for d in family_devices("nugget_earmold")] == [5, 6]
    assert [d.code for d in family_devices("nugget_earmold", Condition.REFERENCE)] == [5]
    assert family_devices("does_not_exist") == ()


def test_enums_labels():
    assert Condition.REFERENCE.value == "reference"
    assert Condition.MEASUREMENT.short == "Meas"
    assert Coupling.EARMOLD.label == "Earmold"
    assert Coupling.DOME.label == "Dome"
    assert Coupling.OPEN.label == "Open ear"
    assert Probe.MEASUREMENT.short == "MPT"
    assert Probe.REFERENCE.short == "RPT"
    assert Source.HEARING_AID_DRIVER.label == "Hearing-aid driver"
    assert Source.LOUDSPEAKER.label == "Loudspeaker"
    assert Quantity.THRESHOLD.value == "threshold"


def test_domain_constants():
    assert P_REF_PA == pytest.approx(20e-6)
    assert U_HA_DRIVE_V == pytest.approx(11.2e-3)
    assert DB_SPL_OFFSET_FROM_PA == pytest.approx(20 * math.log10(1 / 20e-6))
    assert FREQUENCY_RESOLUTION_HZ == pytest.approx(22050.0 / 2048.0)
    assert NYQUIST_HZ == pytest.approx(22050.0)
    assert (N_FREQUENCIES, N_THRESHOLD_FREQUENCIES, N_SUBJECTS, N_REINSERTIONS) == (2049, 6, 14, 3)


# ---------------------------------------------------------------------------
# container structural validity (all 7 containers)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "key, valid_count, predicate",
    [
        ("M_ha2edM", 7, lambda d: d.condition is Condition.MEASUREMENT),
        ("M_ha2edR", 8, lambda d: d.is_earmold),
        ("M_ha2haf", 14, lambda d: True),
        ("M_ls2edM", 7, lambda d: d.condition is Condition.MEASUREMENT),
        ("M_ls2edR", 8, lambda d: d.is_earmold),
        ("M_thr_ha", 14, lambda d: True),
        ("M_REUR", 14, lambda d: True),
    ],
)
def test_structural_validity_rules(key, valid_count, predicate):
    spec = CONTAINERS[key]
    valid = structural_validity(spec)
    assert valid.shape == (14,)
    assert valid.sum() == valid_count
    for spec_device, is_valid in zip(DEVICES, valid):
        assert bool(is_valid) == predicate(spec_device)


def test_container_registry():
    assert len(CONTAINERS) == 7
    assert set(CONTAINERS) == set(CONTAINER_ORDER)
    assert len(CONTAINER_ORDER) == 7
    assert len(TRANSFER_CONTAINER_KEYS) == 5
    assert THRESHOLD_CONTAINER_KEY == "M_thr_ha"
    assert REUR_CONTAINER_KEY == "M_REUR"
    assert CONTAINERS[REUR_CONTAINER_KEY].is_reur
    assert all(not CONTAINERS[k].is_reur for k in TRANSFER_CONTAINER_KEYS)
    for key, spec in CONTAINERS.items():
        assert spec.key == key
        assert spec.rationale


def test_specific_invalid_combinations():
    # Measurement probe in the reference condition is documented as loose.
    assert not CONTAINERS["M_ha2edM"].structural_valid(device(1))
    assert not CONTAINERS["M_ls2edM"].structural_valid(device(1))
    assert CONTAINERS["M_ha2edM"].structural_valid(device(2))
    # Reference probe only exists for earmolds (through the earmold bore).
    assert not CONTAINERS["M_ha2edR"].structural_valid(device(9))
    assert CONTAINERS["M_ha2edR"].structural_valid(device(8))
    assert not CONTAINERS["M_ls2edR"].structural_valid(device(14))
    # Feedback path and thresholds exist for every coupling.
    for code in range(1, 15):
        assert CONTAINERS["M_ha2haf"].structural_valid(device(code))
        assert CONTAINERS["M_thr_ha"].structural_valid(device(code))


# ---------------------------------------------------------------------------
# validity helpers
# ---------------------------------------------------------------------------
def test_finite_mask_complex():
    values = np.array([1 + 1j, np.nan + 0j, np.inf + 0j, np.nan + 1j * np.nan])
    assert finite_mask(values).tolist() == [True, False, False, False]


def test_build_valid_mask_combines_structural_and_measured():
    rng = np.random.default_rng(0)
    values = (rng.standard_normal((5, 14, 2, 2)) + 1j * rng.standard_normal((5, 14, 2, 2)))
    values[1, 2, 0, 0] = np.nan
    spec = CONTAINERS["M_ha2edM"]
    mask = build_valid_mask(values, spec, DEVICES)
    assert mask.shape == values.shape
    assert mask.dtype == bool
    # device index 0 (reference condition) is structurally invalid everywhere.
    assert not mask[:, 0].any()
    # device index 1 (measurement condition) is valid except the planted NaN.
    assert mask[:, 1].all()
    assert not mask[1, 2, 0, 0]
    np.testing.assert_array_equal(combined_valid_mask(values, spec, DEVICES), mask)


def test_structural_validity_table():
    table = structural_validity_table()
    assert isinstance(table, pd.DataFrame)
    assert len(table) == 7 * 14
    assert {"container", "device_code", "structurally_valid"}.issubset(table.columns)
    assert table.groupby("container")["structurally_valid"].sum().to_dict() == {
        "M_ha2edM": 7,
        "M_ha2edR": 8,
        "M_ha2haf": 14,
        "M_ls2edM": 7,
        "M_ls2edR": 8,
        "M_thr_ha": 14,
        "M_REUR": 14,
    }


def test_invalid_reasons_table():
    table = invalid_reasons_table()
    assert isinstance(table, pd.DataFrame)
    assert len(table) == 7
    assert {"container", "valid_conditions", "valid_couplings", "rationale"}.issubset(table.columns)
    row = table.set_index("container").loc["M_ha2edM"]
    assert row["valid_conditions"] == "measurement"
    assert row["valid_couplings"] == "all"
    assert row["n_structurally_valid_devices"] == 7
    assert table.set_index("container").loc["M_ha2edR"]["valid_device_codes"] == "1, 2, 3, 4, 5, 6, 7, 8"


def test_invalid_sessions_4d():
    values = np.ones((6, 14, 2, 2), dtype=complex)
    values[:, 3, 0, 1] = np.nan
    values[:, 5, 1, 0] = np.nan
    table = invalid_sessions(values, freq_axis=0)
    assert table.shape == (14, 2, 2)
    assert table.sum() == 2
    assert table[3, 0, 1] and table[5, 1, 0]


def test_invalid_sessions_threshold():
    values = np.ones((6, 14, 2, 2))
    values[:, 0, 0, 0] = np.nan
    assert invalid_sessions(values, freq_axis=0, threshold=6).sum() == 1
    assert invalid_sessions(values, freq_axis=0, threshold=3).sum() == 1


def test_invalid_sessions_2d():
    values = np.ones((8, 3), dtype=complex)
    values[:, 1] = np.nan
    table = invalid_sessions(values, freq_axis=0)
    assert table.shape == (3,)
    assert table.tolist() == [False, True, False]


def test_build_valid_mask_rejects_wrong_dimensionality():
    spec = CONTAINERS["M_ha2edM"]
    with pytest.raises(ValueError, match="4-D"):
        build_valid_mask(np.zeros((10, 14, 2)), spec, DEVICES)
    with pytest.raises(ValueError, match="device axis"):
        build_valid_mask(np.zeros((10, 3, 2, 2)), spec, DEVICES)


# ---------------------------------------------------------------------------
# unit conversions
# ---------------------------------------------------------------------------
def test_db_spl_offset():
    assert dB_SPL_OFFSET == pytest.approx(93.97940008672037)
    assert dB_SPL_OFFSET == pytest.approx(DB_SPL_OFFSET_FROM_PA)


def test_magnitude_and_nan():
    values = np.array([1.0, -2.0, 3.0 + 4.0j])
    np.testing.assert_allclose(magnitude(values), [1.0, 2.0, 5.0])
    out = magnitude(np.array([np.nan, 1.0]))
    assert np.isnan(out[0]) and out[1] == 1.0


def test_magnitude_db_reference_and_floor():
    np.testing.assert_allclose(magnitude_db(np.array([1.0, 10.0, 0.1])), [0.0, 20.0, -20.0])
    # 1 Pa re 20 µPa is 93.9794 dB SPL.
    assert magnitude_db(np.array([1.0]), reference=P_REF_PA)[0] == pytest.approx(dB_SPL_OFFSET)
    # Zero magnitudes are clamped to the floor instead of -inf.
    assert magnitude_db(np.array([0.0]), floor_db=-120.0)[0] == pytest.approx(-120.0)
    # NaN propagates as NaN.
    assert np.isnan(magnitude_db(np.array([np.nan]))[0])
    with pytest.raises(UnitError, match="reference"):
        magnitude_db(np.array([1.0]), reference=0.0)
    with pytest.raises(UnitError, match="reference"):
        magnitude_db(np.array([1.0]), reference=-20e-6)


def test_phase_conversions_and_nan():
    values = np.array([1.0 + 0j, 0.0 + 1.0j, -1.0 + 0j, 1.0 - 1.0j])
    np.testing.assert_allclose(phase_deg(values), [0.0, 90.0, 180.0, -45.0], atol=1e-12)
    np.testing.assert_allclose(phase_rad(values), np.radians([0.0, 90.0, 180.0, -45.0]))
    assert np.isnan(phase_deg(np.array([np.nan + 0j, 1 + 1j * np.nan]))).all()
    assert np.isnan(phase_rad(np.array([np.nan + 0j]))).all()


def test_pressure_db_roundtrips():
    db_spl = np.array([-20.0, 0.0, 40.0, 94.0])
    pressure = db_to_pa(db_spl)
    np.testing.assert_allclose(pressure, P_REF_PA * 10.0 ** (db_spl / 20.0))
    np.testing.assert_allclose(pa_to_db_spl(pressure), db_spl, rtol=1e-12, atol=1e-12)
    # Amplitude round-trip.
    db = np.array([-40.0, -6.0, 0.0, 12.0])
    np.testing.assert_allclose(magnitude_db(db_to_amplitude(db)), db, atol=1e-12)
    assert db_to_pa(0.0) == pytest.approx(P_REF_PA)


def test_db_pa_per_v_relations():
    # dB re Pa/V and dB re Pa differ by exactly 20 log10(1 / 0.0112).
    pressure = np.array([1e-4, 1e-3, 1.0])
    db_pa = magnitude_db(pressure, reference=1.0)
    db_pa_per_v = pa_to_db_pa_per_v(pressure)
    expected_offset = 20 * math.log10(1.0 / U_HA_DRIVE_V)
    np.testing.assert_allclose(db_pa_per_v - db_pa, expected_offset, atol=1e-12)
    # dB SPL and dB re Pa/V differ by 20 log10(0.0112 / 20e-6) = 54.96 dB.
    db_spl = pa_to_db_spl(pressure)
    np.testing.assert_allclose(
        db_spl - db_pa_per_v, 20 * math.log10(U_HA_DRIVE_V / P_REF_PA), atol=1e-12
    )
    assert pa_to_db_spl(pressure)[0] - pa_to_db_pa_per_v(pressure)[0] == pytest.approx(54.96, abs=0.01)


def test_pa_per_v_invalid_drive_voltage():
    with pytest.raises(UnitError, match="drive voltage"):
        pa_to_db_pa_per_v(np.array([1.0]), drive_voltage_v=0.0)
    with pytest.raises(UnitError, match="drive voltage"):
        pa_to_db_pa_per_v(np.array([1.0]), drive_voltage_v=-0.0112)


def test_threshold_dbv_to_voltage():
    np.testing.assert_allclose(
        threshold_dbv_to_voltage(np.array([0.0, -20.0, -40.0])), [1.0, 0.1, 0.01]
    )
    voltage = threshold_dbv_to_voltage(np.array([-30.0, -60.0]))
    np.testing.assert_allclose(20 * np.log10(voltage), [-30.0, -60.0], atol=1e-12)
