"""Unit tests for :mod:`acousticbench.dsp.metrics`.

Every expected value is computed analytically from the generated signals
(known tone amplitudes, known noise RMS, known filter transfer function).
"""

from __future__ import annotations

import numpy as np
import pytest
import scipy.signal as _signal

from acousticbench.dsp.filters import design_fir
from acousticbench.dsp.metrics import (
    estimate_filter_response,
    estimate_gain_db,
    estimate_snr_db,
    estimate_thd,
    estimate_thd_plus_n,
    tone_component,
)
from acousticbench.dsp.signals import sine, white_noise
from acousticbench.dsp.spectra import welch_psd
from acousticbench.exceptions import MeasurementError

FS = 8000


def _tone_plus_noise(
    amplitude: float,
    tone_hz: float,
    snr_db: float,
    seed: int,
    duration_s: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(clean, noise)`` with an exact analytic SNR."""
    clean = sine(tone_hz, FS, duration_s, amplitude=amplitude)
    noise_rms = (amplitude / np.sqrt(2.0)) / 10.0 ** (snr_db / 20.0)
    noise = white_noise(clean.size, seed=seed, level_dbfs=20.0 * np.log10(noise_rms))
    return clean, noise


def test_tone_component_recovers_amplitude_and_phase() -> None:
    amplitude, phase = 0.4, 0.7
    x = sine(1000.0, FS, 0.5, amplitude=amplitude, phase_rad=phase)
    component = tone_component(x, FS, 1000.0)
    assert component.amplitude == pytest.approx(amplitude, rel=1e-10)
    assert component.phase_rad == pytest.approx(phase, abs=1e-10)
    assert component.rms == pytest.approx(amplitude / np.sqrt(2.0), rel=1e-10)
    assert component.power == pytest.approx(amplitude**2 / 2.0, rel=1e-10)


def test_estimate_gain_tone_method_is_exact_for_known_gain() -> None:
    x_in = sine(1000.0, FS, 0.5, amplitude=0.3)
    x_out = x_in * 10.0 ** (6.5 / 20.0)
    result = estimate_gain_db(x_in, x_out, FS, tone_hz=1000.0)
    assert result.method == "tone"
    assert result.gain_db == pytest.approx(6.5, abs=1e-9)
    assert result.tone_hz == pytest.approx(1000.0)


def test_estimate_gain_tone_method_is_robust_to_noise() -> None:
    x_in = sine(1000.0, FS, 1.0, amplitude=0.2)
    x_out = x_in * 10.0 ** (-3.0 / 20.0) + white_noise(x_in.size, seed=4, level_dbfs=-40.0)
    result = estimate_gain_db(x_in, x_out, FS, tone_hz=1000.0)
    assert result.gain_db == pytest.approx(-3.0, abs=0.01)


def test_estimate_gain_rms_and_band_methods() -> None:
    noise = white_noise(8192, seed=8, level_dbfs=-20.0)
    gained = noise * 2.0
    assert estimate_gain_db(noise, gained, FS).gain_db == pytest.approx(6.0206, abs=1e-3)
    band = estimate_gain_db(noise, gained, FS, band_hz=(500.0, 2000.0))
    assert band.method == "band"
    assert band.gain_db == pytest.approx(6.0206, abs=0.05)


def test_estimate_gain_band_accepts_stats_band() -> None:
    from acousticbench.stats.bands import Band

    noise = white_noise(8192, seed=9, level_dbfs=-20.0)
    band = Band(label="test", center_hz=1000.0, low_hz=500.0, high_hz=2000.0)
    result = estimate_gain_db(noise, noise * 2.0, FS, band_hz=band)
    assert result.gain_db == pytest.approx(6.0206, abs=0.05)


def test_estimate_gain_invalid_inputs_raise() -> None:
    x = sine(1000.0, FS, 0.25)
    with pytest.raises(ValueError):
        estimate_gain_db(x, x[:-1], FS)
    with pytest.raises(ValueError):
        estimate_gain_db(x, x, FS, tone_hz=1000.0, band_hz=(500.0, 1500.0))
    with pytest.raises(MeasurementError):
        estimate_gain_db(np.zeros(x.size), x, FS, tone_hz=1000.0)
    with pytest.raises(MeasurementError):
        estimate_gain_db(np.zeros(x.size), x, FS, tone_hz=1000.0)


def test_estimate_snr_psd_matches_analytic_snr() -> None:
    amplitude, snr = 0.3, 20.0
    clean, noise = _tone_plus_noise(amplitude, 1000.0, snr, seed=21)
    result = estimate_snr_db(clean + noise, FS, 1000.0)
    realised = 10.0 * np.log10(np.mean(clean**2) / np.mean(noise**2))
    assert result.method == "psd"
    assert result.snr_db == pytest.approx(realised, abs=0.2)
    assert result.signal_power == pytest.approx(amplitude**2 / 2.0, rel=0.01)


def test_estimate_snr_residual_matches_analytic_snr() -> None:
    amplitude, snr = 0.3, 10.0
    clean, noise = _tone_plus_noise(amplitude, 1000.0, snr, seed=22)
    result = estimate_snr_db(clean + noise, FS, 1000.0, method="residual")
    realised = 10.0 * np.log10(np.mean(clean**2) / np.mean(noise**2))
    assert result.method == "residual"
    assert result.snr_db == pytest.approx(realised, abs=0.2)


def test_estimate_snr_full_band_equals_explicit_band() -> None:
    clean, noise = _tone_plus_noise(0.3, 1000.0, 15.0, seed=23)
    signal = clean + noise
    default = estimate_snr_db(signal, FS, 1000.0)
    explicit = estimate_snr_db(signal, FS, 1000.0, noise_band_hz=(20.0, FS / 2.0))
    assert explicit.snr_db == pytest.approx(default.snr_db, abs=0.05)


def test_estimate_snr_band_limited_matches_band_power() -> None:
    clean, noise = _tone_plus_noise(0.3, 1000.0, 15.0, seed=24)
    signal = clean + noise
    band = (500.0, 2000.0)
    result = estimate_snr_db(signal, FS, 1000.0, noise_band_hz=band)
    psd = welch_psd(noise, FS, nperseg=1024)
    band_noise_power = psd.band_power(band)
    expected_snr = 10.0 * np.log10(np.mean(clean**2) / band_noise_power)
    assert result.snr_db == pytest.approx(expected_snr, abs=0.5)


def test_estimate_snr_invalid_inputs_raise() -> None:
    clean, noise = _tone_plus_noise(0.3, 1000.0, 10.0, seed=25)
    with pytest.raises(MeasurementError):
        estimate_snr_db(np.zeros(FS), FS, 1000.0)
    with pytest.raises(ValueError):
        estimate_snr_db(clean + noise, FS, 1000.0, noise_band_hz=(100.0, 2000.0), method="bad")
    with pytest.raises(ValueError):
        estimate_snr_db(clean + noise, FS, 1000.0, noise_band_hz=(2000.0, 1000.0))


def _harmonic_signal(
    fundamental_amplitude: float,
    harmonic_percent: tuple[float, ...],
    tone_hz: float = 500.0,
    duration_s: float = 0.5,
) -> tuple[np.ndarray, tuple[float, ...]]:
    """Build a signal with known harmonic amplitudes; return its amplitudes."""
    n = int(round(FS * duration_s))
    time = np.arange(n) / FS
    signal = fundamental_amplitude * np.sin(2.0 * np.pi * tone_hz * time)
    amplitudes = tuple(
        fundamental_amplitude * percent / 100.0 for percent in harmonic_percent
    )
    for multiplier, amplitude in zip(range(2, 2 + len(amplitudes)), amplitudes):
        signal += amplitude * np.sin(2.0 * np.pi * multiplier * tone_hz * time + 0.2)
    return signal, amplitudes


def test_estimate_thd_matches_analytic_harmonics() -> None:
    signal, amplitudes = _harmonic_signal(0.5, (1.0, 2.0, 0.5, 0.25))
    expected_thd = 100.0 * np.sqrt(np.sum(np.square(amplitudes))) / 0.5
    result = estimate_thd(signal, FS, 500.0, n_harmonics=4)
    assert result.n_harmonics == 4
    assert result.thd_percent == pytest.approx(expected_thd, abs=1e-6)
    np.testing.assert_allclose(
        result.harmonic_percent, (1.0, 2.0, 0.5, 0.25), atol=1e-6
    )
    assert result.fundamental_dbfs == pytest.approx(20.0 * np.log10(0.5 / np.sqrt(2.0)), abs=1e-6)


def test_estimate_thd_is_zero_for_pure_tone() -> None:
    result = estimate_thd(sine(500.0, FS, 0.5, amplitude=0.4), FS, 500.0)
    assert result.thd_percent == pytest.approx(0.0, abs=1e-9)
    assert result.thd_plus_n_percent == pytest.approx(0.0, abs=1e-9)


def test_estimate_thd_plus_n_includes_noise() -> None:
    signal, amplitudes = _harmonic_signal(0.5, (1.0, 0.0, 0.0, 0.0))
    noise_rms = 0.5 / np.sqrt(2.0) / 10.0 ** (30.0 / 20.0)
    noisy = signal + white_noise(signal.size, seed=31, level_dbfs=20.0 * np.log10(noise_rms))
    thd = estimate_thd(signal, FS, 500.0, n_harmonics=4)
    thd_n = estimate_thd_plus_n(noisy, FS, 500.0, n_harmonics=4)
    expected = 100.0 * np.sqrt(
        (thd.thd_percent / 100.0) ** 2 + (noise_rms / (0.5 / np.sqrt(2.0))) ** 2
    )
    assert thd_n.thd_plus_n_percent == pytest.approx(expected, rel=0.05)
    assert thd_n.thd_plus_n_percent > thd_n.thd_percent


def test_estimate_thd_plus_n_band_limited_uses_psd() -> None:
    signal, _ = _harmonic_signal(0.5, (1.0, 0.0, 0.0, 0.0))
    noise_rms = 0.5 / np.sqrt(2.0) / 10.0 ** (20.0 / 20.0)
    noisy = signal + white_noise(signal.size, seed=32, level_dbfs=20.0 * np.log10(noise_rms))
    result = estimate_thd_plus_n(noisy, FS, 500.0, n_harmonics=4, noise_band_hz=(20.0, 3500.0))
    assert result.thd_plus_n_percent > 5.0


def test_estimate_thd_validation() -> None:
    signal = sine(500.0, FS, 0.5)
    with pytest.raises(ValueError):
        estimate_thd(signal, FS, 500.0, n_harmonics=0)
    with pytest.raises(ValueError):
        estimate_thd(
            sine(1500.0, FS, 0.5), FS, 1500.0, n_harmonics=5
        )  # 6th harmonic above Nyquist
    with pytest.raises(MeasurementError):
        estimate_thd(np.zeros(4096), FS, 500.0)


def test_estimate_filter_response_recovers_known_fir() -> None:
    filt = design_fir("lowpass", FS, 1000.0, numtaps=129)
    input_signal = white_noise(8192, seed=41, level_dbfs=-20.0)
    output_signal = _signal.lfilter(filt.fir_taps, [1.0], input_signal)
    result = estimate_filter_response(input_signal, output_signal, FS, n_fft=1024)
    passband = np.array([100.0, 300.0, 500.0, 700.0, 900.0])
    _, analytic = _signal.freqz(filt.fir_taps, worN=passband, fs=FS)
    analytic_db = 20.0 * np.log10(np.maximum(np.abs(analytic), 1e-12))
    estimated_db = np.interp(passband, result.frequencies_hz, result.magnitude_db)
    np.testing.assert_allclose(estimated_db, analytic_db, atol=0.5)
    # The stop band must be clearly attenuated.
    stopband = np.interp(np.array([2000.0]), result.frequencies_hz, result.magnitude_db)
    assert float(stopband[0]) < -40.0


def test_estimate_filter_response_phase_matches_delay() -> None:
    delay_samples = 8
    input_signal = white_noise(8192, seed=42, level_dbfs=-20.0)
    output_signal = np.concatenate([np.zeros(delay_samples), input_signal])[: input_signal.size]
    result = estimate_filter_response(input_signal, output_signal, FS, n_fft=1024)
    mask = (result.frequencies_hz > 200.0) & (result.frequencies_hz < 3000.0)
    expected_phase = -360.0 * result.frequencies_hz[mask] * delay_samples / FS
    np.testing.assert_allclose(result.phase_deg[mask], expected_phase, atol=2.0)


def test_estimate_filter_response_smoothing_reduces_variance() -> None:
    input_signal = white_noise(16384, seed=43, level_dbfs=-20.0)
    output_signal = 2.0 * input_signal
    raw = estimate_filter_response(input_signal, output_signal, FS, n_fft=512)
    smoothed = estimate_filter_response(
        input_signal, output_signal, FS, n_fft=512, smoothing_fraction=3.0
    )
    assert np.std(raw.magnitude_db) > np.std(smoothed.magnitude_db)
    assert np.mean(smoothed.magnitude_db) == pytest.approx(6.0206, abs=0.2)


def test_estimate_filter_response_validation() -> None:
    x = white_noise(2048, seed=1)
    with pytest.raises(ValueError):
        estimate_filter_response(x, x[:-1], FS)
    with pytest.raises(ValueError):
        estimate_filter_response(x, x, FS, n_fft=4)
    with pytest.raises(ValueError):
        estimate_filter_response(x, x, FS, smoothing_fraction=0.0)
