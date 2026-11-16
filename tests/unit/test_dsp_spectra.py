"""Unit tests for :mod:`acousticbench.dsp.spectra`.

Analytic checks: a coherent sine produces a known amplitude/phase in its FFT
bin, the Welch PSD integrates to the signal mean-square power (Parseval), and
the STFT places a tone in the correct bin.
"""

from __future__ import annotations

import numpy as np
import pytest

from acousticbench.dsp.signals import sine, white_noise
from acousticbench.dsp.spectra import fft_spectrum, stft, welch_psd

FS = 8000


def test_fft_spectrum_recovers_coherent_sine_amplitude() -> None:
    amplitude = 0.5
    x = sine(1000.0, FS, 0.5, amplitude=amplitude)
    spectrum = fft_spectrum(x, FS)
    assert spectrum.fs == pytest.approx(FS)
    assert spectrum.window == "hann"
    index = int(np.argmin(np.abs(spectrum.frequencies_hz - 1000.0)))
    assert spectrum.frequencies_hz[index] == pytest.approx(1000.0, abs=1e-9)
    assert spectrum.magnitude[index] == pytest.approx(amplitude, rel=1e-6)
    # A sine has an FFT phase of -90 degrees in its positive-frequency bin.
    assert spectrum.phase_deg[index] == pytest.approx(-90.0, abs=1e-6)


def test_fft_spectrum_cosine_phase_is_zero() -> None:
    x = np.cos(2.0 * np.pi * 1000.0 * np.arange(FS // 2) / FS)
    spectrum = fft_spectrum(x, FS)
    index = int(np.argmin(np.abs(spectrum.frequencies_hz - 1000.0)))
    assert spectrum.phase_deg[index] == pytest.approx(0.0, abs=1e-6)
    assert spectrum.magnitude[index] == pytest.approx(1.0, rel=1e-6)


def test_fft_spectrum_frequency_axis_is_one_sided() -> None:
    x = sine(1000.0, FS, 0.25)
    spectrum = fft_spectrum(x, FS)
    expected_bins = x.size // 2 + 1
    assert spectrum.frequencies_hz.shape == (expected_bins,)
    assert spectrum.frequencies_hz[0] == pytest.approx(0.0)
    assert spectrum.frequencies_hz[-1] == pytest.approx(FS / 2.0)
    assert spectrum.magnitude_db.shape == spectrum.frequencies_hz.shape


def test_fft_spectrum_detrend_removes_linear_trend() -> None:
    time = np.arange(FS // 2) / FS
    x = 0.3 * np.sin(2.0 * np.pi * 1000.0 * time)
    with_trend = x + 2.0 * time
    trended = fft_spectrum(with_trend, FS, detrend=True)
    undetrended = fft_spectrum(with_trend, FS, detrend=False)
    assert abs(trended.spectrum[0]) < 1e-6
    assert abs(undetrended.spectrum[0]) > 0.4


def test_fft_spectrum_zero_padding_keeps_amplitude() -> None:
    x = sine(1000.0, FS, 0.5, amplitude=0.25)
    padded = fft_spectrum(x, FS, n_fft=2 * x.size)
    assert padded.frequencies_hz.size == x.size + 1
    index = int(np.argmin(np.abs(padded.frequencies_hz - 1000.0)))
    assert padded.magnitude[index] == pytest.approx(0.25, rel=1e-3)


def test_fft_spectrum_rejects_shorter_fft() -> None:
    with pytest.raises(ValueError):
        fft_spectrum(sine(1000.0, FS, 0.5), FS, n_fft=128)
    with pytest.raises(ValueError):
        fft_spectrum(sine(1000.0, FS, 0.5), FS, window="not-a-window")


def test_stft_shapes_and_tone_bin() -> None:
    x = sine(1000.0, FS, 0.5)
    result = stft(x, FS, nperseg=256, noverlap=128)
    assert result.spectrum.ndim == 2
    assert result.spectrum.shape[0] == 256 // 2 + 1
    assert result.spectrum.shape[1] == result.times_s.size
    frequencies = result.frequencies_hz
    tone_index = int(np.argmin(np.abs(frequencies - 1000.0)))
    frame_magnitude = np.abs(result.spectrum[tone_index, :])
    # scipy's "spectrum" scaling maps a unit sine to 0.5 in its bin.
    assert float(np.median(frame_magnitude)) == pytest.approx(0.5, rel=1e-3)
    assert result.times_s[0] == pytest.approx(256 / FS / 2.0)


def test_stft_hann_windowing_reduces_leakage() -> None:
    x = sine(1037.0, FS, 0.5)  # non-coherent tone
    hann = stft(x, FS, nperseg=256, noverlap=0, window="hann")
    boxcar = stft(x, FS, nperseg=256, noverlap=0, window="boxcar")
    frame = hann.magnitude.shape[1] // 2
    hann_ratio = hann.magnitude[50, frame] / hann.magnitude[:, frame].max()
    boxcar_ratio = boxcar.magnitude[50, frame] / boxcar.magnitude[:, frame].max()
    assert hann_ratio < boxcar_ratio


def test_stft_invalid_parameters_raise() -> None:
    x = sine(1000.0, FS, 0.5)
    with pytest.raises(ValueError):
        stft(x, FS, nperseg=100000)
    with pytest.raises(ValueError):
        stft(x, FS, nperseg=256, noverlap=256)


def test_welch_psd_integrates_to_mean_square() -> None:
    noise = white_noise(16384, seed=2, level_dbfs=-26.0)
    result = welch_psd(noise, FS, nperseg=1024)
    integrated = float(np.sum(result.psd) * result.df)
    mean_square = float(np.mean(np.square(noise)))
    assert integrated == pytest.approx(mean_square, rel=0.02)
    assert result.frequencies_hz[-1] == pytest.approx(FS / 2.0)
    assert result.df == pytest.approx(FS / 1024)


def test_welch_psd_tone_power_matches_analytic() -> None:
    amplitude = 0.4
    x = sine(1000.0, FS, 1.0, amplitude=amplitude)
    result = welch_psd(x, FS, nperseg=4096)
    power = result.band_power((990.0, 1010.0))
    assert power == pytest.approx(amplitude**2 / 2.0, rel=1e-3)


def test_welch_psd_band_power_validation() -> None:
    result = welch_psd(white_noise(4096, seed=1), FS, nperseg=512)
    with pytest.raises(ValueError):
        result.band_power((1000.0, 100.0))
    with pytest.raises(ValueError):
        result.band_power((9000.0, 10000.0))


def test_welch_psd_clamps_long_segments() -> None:
    result = welch_psd(white_noise(256, seed=1), FS, nperseg=4096)
    assert result.nperseg == 256
    assert result.frequencies_hz.size == 256 // 2 + 1
