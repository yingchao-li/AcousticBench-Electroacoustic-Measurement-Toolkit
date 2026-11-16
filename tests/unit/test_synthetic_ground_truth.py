"""Unit tests for :mod:`acousticbench.synthetic.ground_truth`.

The analytic helpers are checked against hand-computable values (e.g. a sine of
known amplitude and RMS, a filter with known DTFT).
"""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.dsp.filters import IirFilter, design_fir
from acousticbench.exceptions import SyntheticCaseError
from acousticbench.synthetic.ground_truth import (
    analytic_filter_response,
    build_synthetic_filter,
    dbfs_from_rms,
    evaluation_mask,
    gain_db_from_rms,
    harmonic_percent_from_amplitudes,
    rms_from_dbfs,
    sine_amplitude_from_dbfs,
    snr_db_from_powers,
    snr_db_from_waveforms,
    thd_percent_from_amplitudes,
    thd_plus_n_percent_from_rms,
)

FS = 8000


def test_rms_dbfs_roundtrip() -> None:
    assert rms_from_dbfs(-20.0) == pytest.approx(0.1, rel=1e-15)
    assert dbfs_from_rms(0.1) == pytest.approx(-20.0, rel=1e-15)
    assert sine_amplitude_from_dbfs(-20.0) == pytest.approx(np.sqrt(2.0) * 0.1, rel=1e-15)
    assert dbfs_from_rms(0.0) == float("-inf")


def test_gain_db_from_rms_matches_definition() -> None:
    assert gain_db_from_rms(0.1, 0.2) == pytest.approx(20.0 * np.log10(2.0), rel=1e-12)
    assert gain_db_from_rms(0.2, 0.2) == pytest.approx(0.0, abs=1e-12)
    assert gain_db_from_rms(0.2, 0.0) == float("-inf")
    with pytest.raises(ValueError):
        gain_db_from_rms(0.0, 0.1)


def test_snr_helpers_are_consistent() -> None:
    power = 0.5**2 / 2.0
    noise_power = power / 10.0 ** (20.0 / 10.0)
    assert snr_db_from_powers(power, noise_power) == pytest.approx(20.0, abs=1e-12)

    time = np.arange(FS) / FS
    clean = 0.5 * np.sin(2.0 * np.pi * 1000.0 * time)
    noise = np.full(FS, 0.01)
    expected = 10.0 * np.log10(np.mean(clean**2) / np.mean(noise**2))
    assert snr_db_from_waveforms(clean, noise) == pytest.approx(expected, rel=1e-12)
    with pytest.raises(ValueError):
        snr_db_from_waveforms(clean, noise[:-1])
    with pytest.raises(ValueError):
        snr_db_from_waveforms(clean, np.zeros_like(clean))


def test_thd_helpers_match_formulas() -> None:
    amplitudes = (0.01, 0.02, 0.005)
    fundamental = 1.0
    expected = 100.0 * np.sqrt(sum(value**2 for value in amplitudes)) / fundamental
    assert thd_percent_from_amplitudes(amplitudes, fundamental) == pytest.approx(
        expected, rel=1e-12
    )
    assert harmonic_percent_from_amplitudes(amplitudes, fundamental) == pytest.approx(
        (1.0, 2.0, 0.5)
    )
    assert thd_percent_from_amplitudes((), fundamental) == 0.0
    with pytest.raises(ValueError):
        thd_percent_from_amplitudes(amplitudes, 0.0)


def test_thd_plus_n_formula() -> None:
    assert thd_plus_n_percent_from_rms(1.0, 0.05) == pytest.approx(5.0, rel=1e-15)
    with pytest.raises(ValueError):
        thd_plus_n_percent_from_rms(0.0, 0.05)


def test_evaluation_mask_uses_documented_dynamic_range() -> None:
    magnitude = np.array([-60.0, -30.0, -20.0, -10.0, -0.5])
    mask = evaluation_mask(magnitude, dynamic_range_db=20.0)
    assert mask.tolist() == [False, False, True, True, True]
    with pytest.raises(ValueError):
        evaluation_mask(magnitude, dynamic_range_db=0.0)
    with pytest.raises(ValueError):
        evaluation_mask(np.array([1.0, np.nan]))


def test_build_synthetic_filter_lowpass_is_fir() -> None:
    filt = build_synthetic_filter(
        {"filter_type": "lowpass", "cutoff_hz": 1000.0, "numtaps": 129}, FS
    )
    assert filt.numtaps == 129
    magnitude_db, phase_deg = analytic_filter_response(
        filt, FS, np.array([100.0, 500.0, 1000.0, 2000.0])
    )
    assert magnitude_db[0] == pytest.approx(0.0, abs=0.05)
    assert magnitude_db[-1] < -40.0
    assert phase_deg.shape == magnitude_db.shape


def test_build_synthetic_filter_bandpass_uses_pair() -> None:
    filt = build_synthetic_filter(
        {"filter_type": "bandpass", "cutoff_hz": (800.0, 2000.0), "numtaps": 129}, FS
    )
    magnitude_db, _ = analytic_filter_response(
        filt, FS, np.array([100.0, 1400.0, 3800.0])
    )
    assert magnitude_db[0] < -40.0
    assert magnitude_db[1] == pytest.approx(0.0, abs=0.1)
    assert magnitude_db[2] < -40.0


def test_build_synthetic_peaking_filter_response_peaks_at_centre() -> None:
    parameters = {
        "filter_type": "peaking",
        "cutoff_hz": 1000.0,
        "peaking_gain_db": 6.0,
        "q": 1.0,
        "numtaps": 129,
    }
    filt = build_synthetic_filter(parameters, FS)
    assert isinstance(filt, IirFilter)
    magnitude_db, _ = analytic_filter_response(
        filt, FS, np.array([100.0, 1000.0, 3000.0])
    )
    assert magnitude_db[1] == pytest.approx(6.0, abs=0.05)
    # Away from the centre the peaking EQ returns to unity (within ~0.1 dB).
    assert magnitude_db[0] == pytest.approx(0.0, abs=0.2)
    assert magnitude_db[2] == pytest.approx(0.0, abs=0.5)


def test_filter_builder_validation() -> None:
    with pytest.raises(SyntheticCaseError):
        build_synthetic_filter({"filter_type": "notch", "cutoff_hz": 1000.0}, FS)
    with pytest.raises(SyntheticCaseError):
        build_synthetic_filter({"filter_type": "lowpass"}, FS)
    with pytest.raises(SyntheticCaseError):
        build_synthetic_filter(
            {"filter_type": "peaking", "cutoff_hz": 1000.0, "q": 1.0}, FS
        )
    with pytest.raises(SyntheticCaseError):
        build_synthetic_filter(
            {"filter_type": "peaking", "cutoff_hz": 1000.0, "peaking_gain_db": 3.0}, FS
        )


def test_analytic_filter_response_matches_direct_dtft() -> None:
    filt = design_fir("lowpass", FS, 1000.0, numtaps=65)
    frequencies = np.array([250.0, 1000.0, 2500.0])
    magnitude_db, _ = analytic_filter_response(filt, FS, frequencies)
    taps = filt.fir_taps
    direct = np.asarray(
        [
            np.sum(taps * np.exp(-2j * np.pi * freq * np.arange(taps.size) / FS))
            for freq in frequencies
        ]
    )
    np.testing.assert_allclose(
        20.0 * np.log10(np.maximum(np.abs(direct), 1e-12)), magnitude_db, atol=1e-9
    )
    with pytest.raises(ValueError):
        analytic_filter_response(filt, FS, np.array([0.0, 100.0]))
    with pytest.raises(ValueError):
        analytic_filter_response(filt, FS, np.array([100.0, 5000.0]))
