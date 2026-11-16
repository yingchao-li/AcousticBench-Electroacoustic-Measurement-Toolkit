"""Analytic ground-truth helpers for the synthetic validation cases.

Every helper in this module is a *closed-form* computation from known
parameters or from the actual generated waveforms; none of them calls a
measurement estimator.  The formulas are documented explicitly so that a
reviewer can verify the expected values by hand.

Formulas
--------
Gain
    ``gain_db = 20 log10(rms(x_out) / rms(x_in))``.
SNR
    ``snr_db = 10 log10(mean(clean**2) / mean(noise**2))`` evaluated on the
    actual generated noise waveform, not on the requested parameter.
THD
    ``thd_percent = 100 * sqrt(sum_k(A_k**2)) / A_1`` where ``A_1`` is the
    fundamental peak amplitude and ``A_k`` the harmonic peak amplitudes.
THD+N
    ``thd_plus_n_percent = 100 * rms(residual) / (A_1 / sqrt(2))`` with
    ``residual = x - fundamental``.
Frequency response
    The exact discrete-time transfer function of the known filter is evaluated
    with :func:`scipy.signal.freqz` / :func:`scipy.signal.sosfreqz` at the
    requested frequencies (a DTFT evaluation, not a measurement).  The
    magnitude is ``20 log10 |H|`` and the phase is the unwrapped angle in
    degrees.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import scipy.signal as _signal

from acousticbench.dsp._validation import as_float64_signal, validate_fs
from acousticbench.dsp.filters import FirFilter, IirFilter, design_fir
from acousticbench.exceptions import SyntheticCaseError
from acousticbench.logging_utils import get_logger

__all__ = [
    "FILTER_TYPES",
    "analytic_filter_response",
    "build_synthetic_filter",
    "dbfs_from_rms",
    "evaluation_mask",
    "gain_db_from_rms",
    "harmonic_percent_from_amplitudes",
    "rms_from_dbfs",
    "sine_amplitude_from_dbfs",
    "snr_db_from_powers",
    "snr_db_from_waveforms",
    "thd_percent_from_amplitudes",
    "thd_plus_n_percent_from_rms",
]

logger = get_logger(__name__)

#: Filter types used by the synthetic frequency-response cases.
FILTER_TYPES: tuple[str, ...] = ("lowpass", "highpass", "bandpass", "peaking")

#: Magnitude floor for dB conversion (≈ -240 dB re 1.0).
_MAGNITUDE_FLOOR: float = 1e-12


def rms_from_dbfs(level_dbfs: float) -> float:
    """Convert an RMS level in dBFS to a linear RMS value."""
    value = float(level_dbfs)
    if not np.isfinite(value):
        raise ValueError(f"level_dbfs must be finite, got {level_dbfs!r}")
    return float(10.0 ** (value / 20.0))


def dbfs_from_rms(rms_value: float) -> float:
    """Convert a linear RMS value to dBFS (``-inf`` for zero)."""
    value = float(rms_value)
    if not np.isfinite(value) or value < 0.0:
        raise ValueError(f"rms_value must be finite and >= 0, got {rms_value!r}")
    if value == 0.0:
        return float("-inf")
    return float(20.0 * np.log10(value))


def sine_amplitude_from_dbfs(level_dbfs: float) -> float:
    """Peak amplitude of a sine whose RMS level is ``level_dbfs`` dBFS.

    ``A = sqrt(2) * 10 ** (level_dbfs / 20)``.
    """
    return float(np.sqrt(2.0) * rms_from_dbfs(level_dbfs))


def gain_db_from_rms(rms_in: float, rms_out: float) -> float:
    """Gain in dB from two RMS values.

    Parameters
    ----------
    rms_in:
        RMS of the input signal (> 0).
    rms_out:
        RMS of the output signal (>= 0).

    Returns
    -------
    float
        ``20 log10(rms_out / rms_in)``; ``-inf`` for a silent output.

    Raises
    ------
    ValueError
        If ``rms_in`` is not strictly positive.
    """
    input_level = float(rms_in)
    output_level = float(rms_out)
    if not np.isfinite(input_level) or input_level <= 0.0:
        raise ValueError(f"rms_in must be finite and > 0, got {rms_in!r}")
    if not np.isfinite(output_level) or output_level < 0.0:
        raise ValueError(f"rms_out must be finite and >= 0, got {rms_out!r}")
    if output_level == 0.0:
        return float("-inf")
    return float(20.0 * np.log10(output_level / input_level))


def snr_db_from_powers(signal_power: float, noise_power: float) -> float:
    """SNR in dB from two mean-square powers.

    ``10 log10(signal_power / noise_power)``.

    Raises
    ------
    ValueError
        If either power is not strictly positive.
    """
    signal_value = float(signal_power)
    noise_value = float(noise_power)
    if not np.isfinite(signal_value) or signal_value <= 0.0:
        raise ValueError(f"signal_power must be finite and > 0, got {signal_power!r}")
    if not np.isfinite(noise_value) or noise_value <= 0.0:
        raise ValueError(f"noise_power must be finite and > 0, got {noise_power!r}")
    return float(10.0 * np.log10(signal_value / noise_value))


def snr_db_from_waveforms(clean: np.ndarray, noise: np.ndarray) -> float:
    """SNR in dB computed from the actual clean and noise waveforms.

    Parameters
    ----------
    clean:
        Noise-free signal waveform.
    noise:
        Noise waveform (same length).

    Returns
    -------
    float
        ``10 log10(mean(clean**2) / mean(noise**2))``.

    Raises
    ------
    ValueError
        If the signals are invalid, of unequal length, or the noise is silent.
    """
    clean_data = as_float64_signal(clean, "clean")
    noise_data = as_float64_signal(noise, "noise")
    if clean_data.size != noise_data.size:
        raise ValueError("clean and noise must have the same length")
    signal_power = float(np.mean(np.square(clean_data)))
    noise_power = float(np.mean(np.square(noise_data)))
    if signal_power <= 0.0:
        raise ValueError("clean signal is silent; SNR is undefined")
    return snr_db_from_powers(signal_power, noise_power)


def thd_percent_from_amplitudes(
    harmonic_amplitudes: Sequence[float],
    fundamental_amplitude: float,
) -> float:
    """THD in percent from harmonic peak amplitudes.

    ``thd = 100 * sqrt(sum(A_k**2)) / A_1``.
    """
    fundamental = float(fundamental_amplitude)
    if not np.isfinite(fundamental) or fundamental <= 0.0:
        raise ValueError(f"fundamental_amplitude must be finite and > 0, got {fundamental_amplitude!r}")
    amplitudes = np.asarray(harmonic_amplitudes, dtype=np.float64)
    if amplitudes.ndim != 1:
        raise ValueError("harmonic_amplitudes must be one-dimensional")
    if amplitudes.size == 0:
        return 0.0
    if not np.all(np.isfinite(amplitudes)):
        raise ValueError("harmonic_amplitudes must be finite")
    return float(100.0 * np.sqrt(np.sum(np.square(amplitudes))) / fundamental)


def harmonic_percent_from_amplitudes(
    harmonic_amplitudes: Sequence[float],
    fundamental_amplitude: float,
) -> tuple[float, ...]:
    """Per-harmonic amplitudes in percent of the fundamental."""
    fundamental = float(fundamental_amplitude)
    if not np.isfinite(fundamental) or fundamental <= 0.0:
        raise ValueError(f"fundamental_amplitude must be finite and > 0, got {fundamental_amplitude!r}")
    amplitudes = np.asarray(harmonic_amplitudes, dtype=np.float64)
    if amplitudes.ndim != 1 or not np.all(np.isfinite(amplitudes)):
        raise ValueError("harmonic_amplitudes must be a finite one-dimensional sequence")
    return tuple(float(100.0 * amplitude / fundamental) for amplitude in amplitudes)


def thd_plus_n_percent_from_rms(
    fundamental_rms: float,
    residual_rms: float,
) -> float:
    """THD+N in percent from the fundamental and residual RMS values.

    ``thd_plus_n = 100 * rms(residual) / rms(fundamental)``.
    """
    fundamental = float(fundamental_rms)
    if not np.isfinite(fundamental) or fundamental <= 0.0:
        raise ValueError(f"fundamental_rms must be finite and > 0, got {fundamental_rms!r}")
    residual = float(residual_rms)
    if not np.isfinite(residual) or residual < 0.0:
        raise ValueError(f"residual_rms must be finite and >= 0, got {residual_rms!r}")
    return float(100.0 * residual / fundamental)


def evaluation_mask(
    magnitude_db: np.ndarray,
    dynamic_range_db: float = 20.0,
) -> np.ndarray:
    """Boolean mask of frequencies within ``dynamic_range_db`` of the peak.

    The documented frequency-response reference condition evaluates the
    magnitude error only inside this mask; deep stop-band frequencies, where
    the true response is far below the pass-band level, are excluded because no
    finite-dynamic-range measurement can resolve them.

    Parameters
    ----------
    magnitude_db:
        True (analytic) magnitude response in dB.
    dynamic_range_db:
        Allowed distance below the maximum magnitude in dB (> 0).

    Returns
    -------
    numpy.ndarray
        Boolean mask with at least one ``True`` entry.
    """
    values = np.asarray(magnitude_db, dtype=np.float64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("magnitude_db must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(values)):
        raise ValueError("magnitude_db contains non-finite values")
    if not np.isfinite(dynamic_range_db) or dynamic_range_db <= 0.0:
        raise ValueError(
            f"dynamic_range_db must be finite and > 0, got {dynamic_range_db!r}"
        )
    peak = float(np.max(values))
    mask = values >= peak - float(dynamic_range_db)
    if not np.any(mask):  # pragma: no cover - the peak bin always satisfies it
        mask[int(np.argmax(values))] = True
    return mask


def _peaking_biquad_sos(fs: float, center_hz: float, gain_db: float, q: float) -> np.ndarray:
    """Return the SOS of an RBJ peaking EQ biquad."""
    if not (0.0 < center_hz < fs / 2.0):
        raise SyntheticCaseError(
            f"peaking centre frequency must be in (0, {fs / 2.0:g}) Hz, got {center_hz!r}"
        )
    if not np.isfinite(q) or q <= 0.0:
        raise SyntheticCaseError(f"peaking Q must be finite and > 0, got {q!r}")
    if not np.isfinite(gain_db):
        raise SyntheticCaseError(f"peaking gain_db must be finite, got {gain_db!r}")
    amplitude = 10.0 ** (float(gain_db) / 40.0)
    omega = 2.0 * np.pi * center_hz / fs
    alpha = np.sin(omega) / (2.0 * q)
    b0 = 1.0 + alpha * amplitude
    b1 = -2.0 * np.cos(omega)
    b2 = 1.0 - alpha * amplitude
    a0 = 1.0 + alpha / amplitude
    a1 = -2.0 * np.cos(omega)
    a2 = 1.0 - alpha / amplitude
    return np.asarray([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]], dtype=np.float64)


def build_synthetic_filter(
    parameters: Mapping[str, Any],
    fs: float,
) -> FirFilter | IirFilter:
    """Design the known filter described by a frequency-response case.

    Parameters
    ----------
    parameters:
        Mapping containing ``filter_type`` and the type-specific design
        parameters:

        * ``lowpass`` / ``highpass``: ``cutoff_hz`` (float) and ``numtaps``.
        * ``bandpass``: ``cutoff_hz`` (``(low_hz, high_hz)`` pair) and
          ``numtaps``.
        * ``peaking``: ``cutoff_hz`` (centre), ``peaking_gain_db`` and ``q``.

    fs:
        Sampling rate in Hz.

    Returns
    -------
    FirFilter or IirFilter
        The designed filter.  The analytic response follows from the returned
        coefficients.

    Raises
    ------
    SyntheticCaseError
        If the parameter mapping is incomplete or invalid.
    """
    rate = validate_fs(fs)
    filter_type = parameters.get("filter_type")
    if filter_type not in FILTER_TYPES:
        raise SyntheticCaseError(
            f"filter_type must be one of {FILTER_TYPES}, got {filter_type!r}"
        )
    if "cutoff_hz" not in parameters:
        raise SyntheticCaseError("frequency-response case is missing cutoff_hz")
    cutoff = parameters["cutoff_hz"]
    if filter_type == "peaking":
        try:
            gain_db = float(parameters["peaking_gain_db"])
            q_value = float(parameters["q"])
        except KeyError as exc:
            raise SyntheticCaseError(
                "peaking filter requires peaking_gain_db and q"
            ) from exc
        sos = _peaking_biquad_sos(rate, float(cutoff), gain_db, q_value)
        return IirFilter(
            kind="peaking",
            fs=rate,
            cutoff_hz=float(cutoff),
            sos=sos,
            order=2,
        )
    numtaps = int(parameters.get("numtaps", 129))
    if filter_type == "bandpass":
        try:
            low, high = float(cutoff[0]), float(cutoff[1])
        except (TypeError, IndexError) as exc:
            raise SyntheticCaseError(
                f"bandpass cutoff_hz must be a (low, high) pair, got {cutoff!r}"
            ) from exc
        return design_fir("bandpass", rate, (low, high), numtaps=numtaps)
    return design_fir(filter_type, rate, float(cutoff), numtaps=numtaps)


def analytic_filter_response(
    filt: FirFilter | IirFilter,
    fs: float,
    frequencies_hz: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate the exact discrete-time response of a known filter.

    Parameters
    ----------
    filt:
        Designed FIR or IIR filter.
    fs:
        Sampling rate in Hz.
    frequencies_hz:
        Frequencies at which to evaluate the DTFT.

    Returns
    -------
    tuple of numpy.ndarray
        ``(magnitude_db, phase_deg)``.  The magnitude is floored at ≈ -240 dB
        and the phase is unwrapped.
    """
    rate = validate_fs(fs)
    frequencies = np.asarray(frequencies_hz, dtype=np.float64)
    if frequencies.ndim != 1 or frequencies.size == 0:
        raise ValueError("frequencies_hz must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(frequencies)):
        raise ValueError("frequencies_hz contains non-finite values")
    if np.any(frequencies <= 0.0) or np.any(frequencies >= rate / 2.0):
        raise ValueError(f"frequencies_hz must be inside (0, {rate / 2.0:g}) Hz")
    if isinstance(filt, FirFilter):
        _, response = _signal.freqz(filt.fir_taps, worN=frequencies, fs=rate)
    elif isinstance(filt, IirFilter):
        _, response = _signal.sosfreqz(filt.sos, worN=frequencies, fs=rate)
    else:
        raise TypeError(
            f"filt must be a FirFilter or IirFilter, got {type(filt).__name__}"
        )
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(response), _MAGNITUDE_FLOOR))
    phase_deg = np.degrees(np.unwrap(np.angle(response)))
    return (
        np.asarray(magnitude_db, dtype=np.float64),
        np.asarray(phase_deg, dtype=np.float64),
    )
