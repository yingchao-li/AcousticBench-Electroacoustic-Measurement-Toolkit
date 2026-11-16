"""Unit tests for :mod:`acousticbench.dsp.signals`.

All checks use analytic ground truth (RMS levels, instantaneous frequency of a
log sweep, SNR of added noise), not hard-coded "pass" values.
"""

from __future__ import annotations

import numpy as np
import pytest
import scipy.signal as _signal

from acousticbench.dsp.signals import (
    add_awgn,
    apply_gain_db,
    dbfs,
    log_sweep,
    multi_tone,
    pink_noise,
    rms,
    sine,
    white_noise,
)

FS = 8000


def test_sine_amplitude_rms_and_length() -> None:
    x = sine(1000.0, FS, 0.5, amplitude=0.5)
    assert x.dtype == np.float64
    assert x.shape == (FS // 2,)
    # A sine of peak amplitude A has RMS A / sqrt(2).
    assert rms(x) == pytest.approx(0.5 / np.sqrt(2.0), rel=1e-12)


def test_sine_matches_analytic_formula() -> None:
    freq, phase, amplitude = 1000.0, 0.3, 0.25
    x = sine(freq, FS, 0.25, amplitude=amplitude, phase_rad=phase)
    t = np.arange(x.size) / FS
    expected = amplitude * np.sin(2.0 * np.pi * freq * t + phase)
    np.testing.assert_allclose(x, expected, atol=1e-15)


def test_sine_spectral_peak_is_at_requested_frequency() -> None:
    x = sine(1000.0, FS, 0.5)
    spectrum = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(x.size, d=1.0 / FS)
    assert freqs[int(np.argmax(spectrum))] == pytest.approx(1000.0, abs=1e-9)


def test_multi_tone_is_sum_of_individual_tones() -> None:
    freqs = (500.0, 1000.0, 1500.0)
    amplitudes = (0.2, 0.3, 0.4)
    combined = multi_tone(freqs, FS, 0.25, amplitudes=amplitudes)
    expected = sum(
        sine(freq, FS, 0.25, amplitude=amplitude)
        for freq, amplitude in zip(freqs, amplitudes)
    )
    np.testing.assert_allclose(combined, expected, atol=1e-12)


def test_white_noise_is_reproducible_and_level_correct() -> None:
    first = white_noise(4096, seed=123, level_dbfs=-20.0)
    second = white_noise(4096, seed=123, level_dbfs=-20.0)
    other = white_noise(4096, seed=124, level_dbfs=-20.0)
    np.testing.assert_array_equal(first, second)
    assert not np.array_equal(first, other)
    assert first.dtype == np.float64
    assert rms(first) == pytest.approx(0.1, rel=1e-12)
    assert rms(white_noise(1024, seed=1)) == pytest.approx(1.0, rel=1e-12)


def test_pink_noise_has_constant_relative_octave_power() -> None:
    samples = pink_noise(65536, seed=7)
    assert rms(samples) == pytest.approx(1.0, rel=1e-10)
    freqs, psd = _signal.welch(samples, fs=FS, nperseg=2048, noverlap=1024)
    density = lambda low, high: float(np.mean(psd[(freqs >= low) & (freqs < high)]))
    # 1/f power density halves per octave: density(200-400) / density(400-800) ≈ 2.
    assert density(200.0, 400.0) / density(400.0, 800.0) == pytest.approx(2.0, rel=0.15)


def test_pink_noise_is_reproducible() -> None:
    np.testing.assert_array_equal(pink_noise(2048, seed=5), pink_noise(2048, seed=5))
    assert not np.array_equal(pink_noise(2048, seed=5), pink_noise(2048, seed=6))


def test_log_sweep_instantaneous_frequency_follows_exponential_law() -> None:
    f_start, f_end, duration = 100.0, 3000.0, 1.0
    x = log_sweep(f_start, f_end, duration, FS, amplitude=0.5)
    analytic = _signal.hilbert(x)
    phase = np.unwrap(np.angle(analytic))
    instantaneous = np.diff(phase) * FS / (2.0 * np.pi)
    times = np.arange(instantaneous.size) / FS
    expected = f_start * (f_end / f_start) ** (times / duration)
    valid = (times > 0.05) & (times < 0.95)
    relative_error = np.abs(instantaneous[valid] - expected[valid]) / expected[valid]
    assert float(np.max(relative_error)) < 0.05


def test_log_sweep_reaches_end_frequency() -> None:
    f_start, f_end, duration = 100.0, 2000.0, 0.5
    x = log_sweep(f_start, f_end, duration, FS)
    analytic = _signal.hilbert(x)
    instantaneous = np.diff(np.unwrap(np.angle(analytic))) * FS / (2.0 * np.pi)
    times = np.arange(instantaneous.size) / FS
    expected = f_start * (f_end / f_start) ** (times / duration)
    # Hilbert-edge effects corrupt the last samples; compare in the interior.
    near_start = int(0.05 * instantaneous.size)
    near_end = int(0.95 * instantaneous.size)
    assert instantaneous[near_start] == pytest.approx(expected[near_start], rel=0.05)
    assert instantaneous[near_end] == pytest.approx(expected[near_end], rel=0.05)


def test_add_awgn_realises_requested_snr() -> None:
    clean = sine(1000.0, FS, 1.0, amplitude=0.5)
    noisy = add_awgn(clean, 20.0, seed=11)
    noise = noisy - clean
    realised = 10.0 * np.log10(np.mean(clean**2) / np.mean(noise**2))
    assert realised == pytest.approx(20.0, abs=0.25)


def test_add_awgn_is_reproducible() -> None:
    clean = sine(1000.0, FS, 0.5)
    np.testing.assert_array_equal(add_awgn(clean, 10.0, seed=3), add_awgn(clean, 10.0, seed=3))


def test_dbfs_and_apply_gain_are_consistent() -> None:
    x = sine(1000.0, FS, 0.5, amplitude=0.5)
    assert dbfs(x) == pytest.approx(20.0 * np.log10(0.5 / np.sqrt(2.0)), rel=1e-12)
    assert dbfs(apply_gain_db(x, 6.0)) == pytest.approx(dbfs(x) + 6.0, abs=1e-12)
    assert dbfs(np.zeros(16)) == float("-inf")


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        sine(FS / 2.0, FS, 0.1)  # at Nyquist
    with pytest.raises(ValueError):
        sine(1000.0, 0.0, 0.1)
    with pytest.raises(ValueError):
        multi_tone([1000.0], FS, 0.1, amplitudes=[1.0, 2.0])
    with pytest.raises(ValueError):
        white_noise(0)
    with pytest.raises(ValueError):
        rms(np.array([0.0, np.inf]))
    with pytest.raises(ValueError):
        add_awgn(np.zeros(128), 10.0)
    with pytest.raises(ValueError):
        log_sweep(2000.0, 1000.0, 0.1, FS)
    with pytest.raises(ValueError):
        apply_gain_db(np.ones(8), float("nan"))
