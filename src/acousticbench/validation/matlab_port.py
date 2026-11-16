"""Independent, MATLAB-transcribed reference implementations.

This module deliberately re-implements the core estimators with a *different*
algorithmic route than the production DSP layer:

* the production estimators use SciPy's coherent projections, Welch averaging
  and IIR/FIR helpers,
* this module uses direct FFTs / DTFT sums written from scratch, mirroring the
  independent MATLAB implementation in ``matlab/+acousticbench/``.

Its purpose is twofold:

1. it is the Python side of the MATLAB cross-language export
   (``matlab/run_cross_language_export.m``),
2. it provides a "MATLAB-code-equivalent" numerical reference that can be
   compared with the production layer **even when MATLAB is not installed**.

Agreement between this port and the production layer is evidence of
algorithmic consistency; it is *not* a substitute for actually executing the
MATLAB code.  The validation report keeps these two statements strictly
separate.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import warnings

import numpy as np
import pandas as pd

from acousticbench.data.dataset import AcousticDataset
from acousticbench.stats.bands import Band
from acousticbench.types import Condition, DEVICES, Coupling

__all__ = [
    "band_levels_from_transfer_port",
    "band_levels_port",
    "fir_dtft_port",
    "gain_db_port",
    "hha_band_levels_port",
    "ptpe_hha_band_levels_port",
    "reoig_band_levels_port",
    "snr_db_port",
    "thd_percent_port",
    "tone_amplitude_port",
]


def _coherent_amplitude(signal: np.ndarray, fs: float, frequency_hz: float) -> float:
    """Amplitude of a coherent sinusoid via a direct DFT projection."""
    data = np.asarray(signal, dtype=np.float64)
    time = np.arange(data.size, dtype=np.float64) / float(fs)
    basis = np.exp(-2j * np.pi * float(frequency_hz) * time)
    return float(2.0 * np.abs(np.sum(data * basis)) / data.size)


def tone_amplitude_port(signal: np.ndarray, fs: float, frequency_hz: float) -> float:
    """Public alias of the direct DFT tone projection."""
    return _coherent_amplitude(signal, fs, frequency_hz)


def gain_db_port(
    x_in: np.ndarray, x_out: np.ndarray, fs: float, tone_hz: float
) -> float:
    """Gain from the ratio of two direct DFT tone amplitudes."""
    amplitude_in = _coherent_amplitude(x_in, fs, tone_hz)
    amplitude_out = _coherent_amplitude(x_out, fs, tone_hz)
    if amplitude_in <= 0.0:
        return float("nan")
    return float(20.0 * np.log10(amplitude_out / amplitude_in))


def snr_db_port(signal: np.ndarray, fs: float, tone_hz: float) -> float:
    """SNR via Parseval: signal bin power vs. total minus signal power."""
    data = np.asarray(signal, dtype=np.float64)
    time = np.arange(data.size, dtype=np.float64) / float(fs)
    amplitude = _coherent_amplitude(data, fs, tone_hz)
    signal_power = 0.5 * amplitude**2
    total_power = float(np.mean(np.square(data)))
    noise_power = total_power - signal_power
    if noise_power <= 0.0 or signal_power <= 0.0:
        return float("nan")
    return float(10.0 * np.log10(signal_power / noise_power))


def thd_percent_port(
    signal: np.ndarray, fs: float, tone_hz: float, n_harmonics: int = 4
) -> float:
    """THD from direct DFT harmonic amplitudes."""
    fundamental = _coherent_amplitude(signal, fs, tone_hz)
    if fundamental <= 0.0:
        return float("nan")
    harmonic_squares = 0.0
    for multiplier in range(2, n_harmonics + 2):
        harmonic_squares += _coherent_amplitude(signal, fs, multiplier * tone_hz) ** 2
    return float(100.0 * np.sqrt(harmonic_squares) / fundamental)


def band_levels_port(
    signal: np.ndarray,
    fs: float,
    bands: Sequence[Band],
    reference: float = 1.0,
) -> pd.DataFrame:
    """Band levels of a time signal via a direct FFT power average."""
    data = np.asarray(signal, dtype=np.float64)
    n = data.size
    spectrum = np.fft.rfft(data)
    power = (np.abs(spectrum) ** 2) / (n**2)
    frequencies = np.fft.rfftfreq(n, d=1.0 / fs)
    rows = []
    for band in bands:
        mask = band.contains(frequencies)
        if not mask.any():
            continue
        power_value = float(np.mean(power[mask]))
        level = 10.0 * np.log10(max(power_value, 1e-30) / reference**2)
        rows.append({"band": band.label, "band_center_hz": band.center_hz, "level_db": level})
    return pd.DataFrame(rows)


def band_levels_from_transfer_port(
    values: np.ndarray,
    frequencies_hz: np.ndarray,
    bands: Sequence[Band],
    reference: float = 1.0,
) -> dict[str, float]:
    """Band power average of a complex transfer array over axis 0."""
    array = np.asarray(values)
    frequencies = np.asarray(frequencies_hz)
    power = np.abs(array) ** 2
    result: dict[str, float] = {}
    for band in bands:
        mask = band.contains(frequencies)
        if not mask.any():
            continue
        with warnings.catch_warnings(), np.errstate(invalid="ignore"):
            warnings.simplefilter("ignore", category=RuntimeWarning)
            mean_power = np.nanmean(power[mask], axis=0)
        result[band.label] = 10.0 * np.log10(
            np.maximum(mean_power, 1e-30) / reference**2
        )
    return result


def fir_dtft_port(taps: np.ndarray, fs: float, frequencies_hz: np.ndarray) -> np.ndarray:
    """Direct DTFT of an FIR filter (independent of scipy.signal.freqz)."""
    coefficients = np.asarray(taps, dtype=np.float64)
    frequencies = np.asarray(frequencies_hz, dtype=np.float64)
    n = np.arange(coefficients.size, dtype=np.float64)
    response = np.zeros(frequencies.size, dtype=np.complex128)
    for index, frequency in enumerate(frequencies):
        response[index] = np.sum(coefficients * np.exp(-2j * np.pi * frequency * n / fs))
    return 20.0 * np.log10(np.maximum(np.abs(response), 1e-12))


# ---------------------------------------------------------------------------
# Dataset-level reference quantities (mirrors matlab/+acousticbench)
# ---------------------------------------------------------------------------
def _median_band_frame(
    values: np.ndarray,
    frequencies_hz: np.ndarray,
    bands: Sequence[Band],
    *,
    reference: float,
) -> pd.DataFrame:
    levels = band_levels_from_transfer_port(values, frequencies_hz, bands, reference)
    rows = []
    centers = {band.label: band.center_hz for band in bands}
    for band_label, array in levels.items():
        rows.append(
            {
                "band": band_label,
                "band_center_hz": float(centers[band_label]),
                "median_db": float(np.nanmedian(array)),
                "n_values": int(np.sum(np.isfinite(array))),
            }
        )
    return pd.DataFrame(rows)


def hha_band_levels_port(
    dataset: AcousticDataset,
    bands: Sequence[Band],
) -> pd.DataFrame:
    """Median Hha band levels (dB SPL) per earmold device, reference probe."""
    frequencies = dataset.frequency_hz
    rows = []
    raw = dataset.values("M_ha2edR")
    for device in DEVICES:
        if device.coupling is not Coupling.EARMOLD or device.condition is not Condition.MEASUREMENT:
            continue
        values = raw[:, device.code - 1, :, :]
        frame = _median_band_frame(values, frequencies, bands, reference=20e-6)
        frame["device_code"] = device.code
        frame["family"] = device.family
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def reoig_band_levels_port(
    dataset: AcousticDataset,
    bands: Sequence[Band],
) -> pd.DataFrame:
    """Median REOIG band levels per family, measurement condition.

    Power ratio of the occluded and open-ear band powers, aggregated per
    subject/reinsertion before taking the median in dB.
    """
    frequencies = dataset.frequency_hz
    reur = np.abs(dataset.values("M_REUR")) ** 2  # (frequency, subject)
    raw = dataset.values("M_ls2edM")
    rows = []
    for device in DEVICES:
        if device.condition is not Condition.MEASUREMENT:
            continue
        occluded = np.abs(raw[:, device.code - 1, :, :]) ** 2  # (freq, subject, reinsertion)
        for band in bands:
            mask = band.contains(frequencies)
            if not mask.any():
                continue
            with warnings.catch_warnings(), np.errstate(invalid="ignore"):
                warnings.simplefilter("ignore", category=RuntimeWarning)
                numerator = np.nanmean(occluded[mask], axis=0)  # (subject, reinsertion)
                denominator = np.nanmean(reur[mask], axis=0)  # (subject,)
            ratio = numerator / np.maximum(denominator[:, None], 1e-30)
            rows.append(
                {
                    "family": device.family,
                    "band": band.label,
                    "band_center_hz": float(band.center_hz),
                    "median_db": float(
                        np.nanmedian(10.0 * np.log10(np.maximum(ratio, 1e-30)))
                    ),
                }
            )
    return pd.DataFrame(rows)


def ptpe_hha_band_levels_port(
    dataset: AcousticDataset,
    bands: Sequence[Band],
) -> pd.DataFrame:
    """Median ΔHha band levels per earmold family (reference probe both conditions)."""
    frequencies = dataset.frequency_hz
    raw = dataset.values("M_ha2edR")
    rows = []
    families = list(dict.fromkeys(d.family for d in DEVICES if d.coupling is Coupling.EARMOLD))
    for family in families:
        measurement = next(
            d for d in DEVICES if d.family == family and d.condition is Condition.MEASUREMENT
        )
        reference_device = next(
            d for d in DEVICES if d.family == family and d.condition is Condition.REFERENCE
        )
        power_measurement = np.abs(raw[:, measurement.code - 1, :, :]) ** 2
        power_reference = np.abs(raw[:, reference_device.code - 1, :, :]) ** 2
        for band in bands:
            mask = band.contains(frequencies)
            if not mask.any():
                continue
            with warnings.catch_warnings(), np.errstate(invalid="ignore"):
                warnings.simplefilter("ignore", category=RuntimeWarning)
                ratio = np.nanmean(power_measurement[mask], axis=0) / np.maximum(
                    np.nanmean(power_reference[mask], axis=0), 1e-30
                )
            rows.append(
                {
                    "family": family,
                    "band": band.label,
                    "band_center_hz": float(band.center_hz),
                    "median_db": float(np.nanmedian(10.0 * np.log10(np.maximum(ratio, 1e-30)))),
                }
            )
    return pd.DataFrame(rows)
