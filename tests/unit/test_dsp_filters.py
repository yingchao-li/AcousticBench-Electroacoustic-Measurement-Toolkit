"""Unit tests for :mod:`acousticbench.dsp.filters`.

The FIR/IIR responses are checked against the analytic filter theory:
Butterworth magnitude is -3.0103 dB at the cutoff, a windowed low-pass FIR is
symmetric (linear phase) and attenuates its stop band, and the zero-phase
``filtfilt`` magnitude equals the square of the one-pass magnitude.
"""

from __future__ import annotations

import numpy as np
import pytest
import scipy.signal as _signal

from acousticbench.dsp.filters import (
    FirFilter,
    IirFilter,
    apply_filter,
    design_fir,
    design_iir,
    frequency_response,
)
from acousticbench.dsp.signals import sine

FS = 8000


def _response_at(filt, fs: float, freq_hz: float) -> float:
    """Exact magnitude in dB of a filter at one frequency (analytic check)."""
    frequency = np.array([freq_hz])
    if isinstance(filt, FirFilter):
        _, response = _signal.freqz(filt.fir_taps, worN=frequency, fs=fs)
    else:
        _, response = _signal.sosfreqz(filt.sos, worN=frequency, fs=fs)
    return float(20.0 * np.log10(np.maximum(np.abs(response), 1e-12))[0])


def test_design_fir_lowpass_is_symmetric_and_attenuates_stopband() -> None:
    filt = design_fir("lowpass", FS, 1000.0, numtaps=129)
    assert isinstance(filt, FirFilter)
    assert filt.fir_taps.shape == (129,)
    assert filt.fir_taps.dtype == np.float64
    assert filt.taps is filt.fir_taps
    np.testing.assert_allclose(filt.fir_taps[::-1], filt.fir_taps, atol=1e-15)
    assert _response_at(filt, FS, 100.0) == pytest.approx(0.0, abs=0.05)
    assert _response_at(filt, FS, 3000.0) < -40.0


def test_design_fir_highpass_attenuates_low_frequencies() -> None:
    filt = design_fir("highpass", FS, 1000.0, numtaps=129)
    assert _response_at(filt, FS, 100.0) < -40.0
    assert _response_at(filt, FS, 3000.0) == pytest.approx(0.0, abs=0.1)


def test_design_fir_bandpass_and_bandstop() -> None:
    bandpass = design_fir("bandpass", FS, (1000.0, 2000.0), numtaps=201)
    bandstop = design_fir("bandstop", FS, (1000.0, 2000.0), numtaps=201)
    assert _response_at(bandpass, FS, 1500.0) == pytest.approx(0.0, abs=0.1)
    assert _response_at(bandpass, FS, 200.0) < -40.0
    assert _response_at(bandstop, FS, 1500.0) < -40.0
    assert _response_at(bandstop, FS, 200.0) == pytest.approx(0.0, abs=0.1)


def test_design_iir_butterworth_is_minus_3db_at_cutoff() -> None:
    filt = design_iir("lowpass", FS, 1000.0, order=4)
    assert isinstance(filt, IirFilter)
    assert filt.sos.shape == (2, 6)
    assert _response_at(filt, FS, 1000.0) == pytest.approx(-3.0103, abs=1e-3)
    assert _response_at(filt, FS, 100.0) == pytest.approx(0.0, abs=0.05)


def test_design_iir_highpass_and_bandpass() -> None:
    highpass = design_iir("highpass", FS, 1000.0, order=2)
    assert _response_at(highpass, FS, 1000.0) == pytest.approx(-3.0103, abs=1e-3)
    assert _response_at(highpass, FS, 200.0) < -20.0
    bandpass = design_iir("bandpass", FS, (500.0, 2000.0), order=2)
    assert _response_at(bandpass, FS, 1000.0) == pytest.approx(0.0, abs=0.1)
    assert _response_at(bandpass, FS, 3500.0) < -20.0


def test_apply_fir_filter_passband_and_stopband() -> None:
    filt = design_fir("lowpass", FS, 1000.0, numtaps=129)
    passband = apply_filter(sine(300.0, FS, 0.5, amplitude=0.5), filt)
    stopband = apply_filter(sine(3000.0, FS, 0.5, amplitude=0.5), filt)
    assert np.sqrt(np.mean(passband**2)) == pytest.approx(0.5 / np.sqrt(2.0), rel=0.02)
    assert np.sqrt(np.mean(stopband**2)) < 0.01 * np.sqrt(np.mean((0.5) ** 2))


def test_apply_iir_filter_is_causal_and_reproducible() -> None:
    filt = design_iir("lowpass", FS, 1000.0, order=4)
    x = sine(1000.0, FS, 0.5, amplitude=0.5)
    first = apply_filter(x, filt)
    second = apply_filter(x, filt)
    np.testing.assert_array_equal(first, second)
    assert first.shape == x.shape
    assert np.max(np.abs(first)) <= np.max(np.abs(x)) + 1e-9


def test_zero_phase_filtering_squares_the_magnitude() -> None:
    filt = design_iir("lowpass", FS, 1000.0, order=2)
    x = sine(1000.0, FS, 1.0, amplitude=1.0)
    one_pass = np.sqrt(np.mean(apply_filter(x, filt) ** 2))
    zero_phase = np.sqrt(np.mean(apply_filter(x, filt, zero_phase=True) ** 2))
    # Sine RMS is 1/sqrt(2); at the cutoff |H| ~ 0.7071 so one pass gives 0.5,
    # and filtfilt squares the magnitude, giving 1/sqrt(8) ~ 0.3536.
    assert one_pass == pytest.approx(0.5, rel=0.01)
    assert zero_phase == pytest.approx(1.0 / np.sqrt(8.0), rel=0.01)


def test_apply_filter_accepts_bare_taps() -> None:
    filt = design_fir("lowpass", FS, 1000.0, numtaps=65)
    x = sine(500.0, FS, 0.25, amplitude=0.3)
    np.testing.assert_array_equal(apply_filter(x, filt), apply_filter(x, filt.fir_taps))


def test_frequency_response_grid_and_phase() -> None:
    filt = design_fir("lowpass", FS, 1000.0, numtaps=129)
    result = frequency_response(filt, FS, n_freqs=1024)
    assert result.frequencies_hz.shape == (1024,)
    assert result.frequencies_hz[0] == pytest.approx(0.0)
    assert result.frequencies_hz[-1] == pytest.approx(FS / 2.0)
    assert result.phase_deg[0] == pytest.approx(0.0)
    # A linear-phase FIR has a linear phase response: group delay = (N-1)/2.
    # Fit only in the pass band, where the magnitude is non-zero (at the
    # stop-band zeros the phase jumps by 180 degrees and unwrapping is
    # ambiguous).
    passband = result.frequencies_hz < 800.0
    slope = np.polyfit(
        result.frequencies_hz[passband], result.phase_deg[passband], 1
    )[0]
    assert -slope * FS / 360.0 == pytest.approx((129 - 1) / 2.0, rel=0.03)


def test_frequency_response_matches_direct_dtft() -> None:
    filt = design_fir("bandpass", FS, (800.0, 2500.0), numtaps=101)
    frequencies = np.array([200.0, 900.0, 1700.0, 3500.0])
    result = frequency_response(filt, FS, n_freqs=FS // 2 + 1)
    direct = np.asarray(
        [
            np.sum(filt.fir_taps * np.exp(-2j * np.pi * freq * np.arange(filt.numtaps) / FS))
            for freq in frequencies
        ]
    )
    expected_db = 20.0 * np.log10(np.maximum(np.abs(direct), 1e-12))
    interpolated = np.interp(frequencies, result.frequencies_hz, result.magnitude_db)
    np.testing.assert_allclose(interpolated, expected_db, atol=0.05)


def test_invalid_filter_designs_raise() -> None:
    with pytest.raises(ValueError):
        design_fir("peaking", FS, 1000.0)
    with pytest.raises(ValueError):
        design_fir("lowpass", FS, 5000.0)
    with pytest.raises(ValueError):
        design_fir("bandpass", FS, 1000.0)
    with pytest.raises(ValueError):
        design_fir("bandpass", FS, (2000.0, 1000.0))
    with pytest.raises(ValueError):
        design_fir("lowpass", FS, 1000.0, numtaps=2)
    with pytest.raises(ValueError):
        design_iir("lowpass", FS, 1000.0, order=0)
    with pytest.raises(ValueError):
        design_iir("highpass", FS, -10.0)
    with pytest.raises(TypeError):
        apply_filter(np.ones(64), "not a filter")
    with pytest.raises(ValueError):
        apply_filter(np.ones(64), np.zeros(16))
    with pytest.raises(ValueError):
        frequency_response(design_fir("lowpass", FS, 1000.0), FS, n_freqs=1)
