"""Deterministic fault injection for virtual hearing-aid validation.

Each fault reproduces a well-defined, physically plausible defect and reports
the *true* parameters it applied, so that detection/localisation algorithms can
be scored against ground truth.  All faults are deterministic: the same input
signal and parameters always produce exactly the same output.

Supported fault types
----------------------
``clipping``
    Hard amplitude clipping at ``clip_level_dbfs`` (or a linear
    ``clip_level``).
``dropout``
    The signal is muted between ``start_s`` and ``stop_s``.
``dc_offset``
    A constant linear ``offset`` is added.
``gain_error``
    A broadband gain error of ``gain_db``.
``harmonic_distortion``
    A known total harmonic distortion (``percentage`` of the fundamental) is
    added on top of the signal's dominant tone (or an explicit ``tone_hz``).
``latency``
    The signal is delayed by ``delay_ms`` (rounded to whole samples).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from acousticbench.dsp._validation import ArrayLike, as_float64_signal, validate_fs
from acousticbench.dsp.metrics import tone_component
from acousticbench.logging_utils import get_logger

__all__ = ["FAULT_TYPES", "FaultResult", "inject_fault"]

logger = get_logger(__name__)

#: Fault types accepted by :func:`inject_fault`.
FAULT_TYPES: tuple[str, ...] = (
    "clipping",
    "dropout",
    "dc_offset",
    "gain_error",
    "harmonic_distortion",
    "latency",
)

#: Amplitude floor below which tone analysis is considered to have failed.
_AMPLITUDE_FLOOR: float = 1e-9


@dataclass(frozen=True, slots=True)
class FaultResult:
    """Output of a fault injection.

    Attributes
    ----------
    output:
        Faulty signal (``float64``, same length as the input).
    fault_type:
        Fault name (one of :data:`FAULT_TYPES`).
    true_params:
        The parameters actually applied, including derived values such as the
        integer delay in samples or the harmonic frequencies.
    description:
        Human-readable description of the injected fault.
    fs:
        Sampling rate in Hz.
    """

    output: np.ndarray
    fault_type: str
    true_params: Mapping[str, Any]
    description: str
    fs: float


def _check_allowed(fault_type: str, params: Mapping[str, Any], allowed: set[str]) -> None:
    """Reject unknown fault parameters (typos must not pass silently)."""
    unexpected = set(params) - allowed
    if unexpected:
        raise ValueError(
            f"unknown parameter(s) {sorted(unexpected)!r} for fault {fault_type!r}; "
            f"allowed: {sorted(allowed)!r}"
        )


def _estimate_dominant_tone(signal: np.ndarray, fs: float) -> float:
    """Return the frequency of the dominant spectral peak (excluding DC)."""
    spectrum = np.abs(np.fft.rfft(signal))
    frequencies = np.fft.rfftfreq(signal.size, d=1.0 / fs)
    if spectrum.size <= 1:
        raise ValueError("signal is too short to estimate a dominant tone")
    spectrum = spectrum.copy()
    spectrum[0] = 0.0
    peak = int(np.argmax(spectrum))
    frequency = float(frequencies[peak])
    if frequency <= 0.0 or spectrum[peak] <= 0.0:
        raise ValueError("signal contains no detectable tone for harmonic distortion")
    return frequency


def _inject_clipping(
    data: np.ndarray, fs: float, params: Mapping[str, Any]
) -> tuple[np.ndarray, dict[str, Any], str]:
    _check_allowed("clipping", params, {"clip_level_dbfs", "clip_level"})
    if "clip_level_dbfs" in params and "clip_level" in params:
        raise ValueError("specify either clip_level_dbfs or clip_level, not both")
    if "clip_level" in params:
        level = float(params["clip_level"])
        if not np.isfinite(level) or level <= 0.0:
            raise ValueError(f"clip_level must be finite and > 0, got {params['clip_level']!r}")
        level_dbfs = 20.0 * np.log10(level)
    else:
        level_dbfs = float(params.get("clip_level_dbfs", -6.0))
        if not np.isfinite(level_dbfs):
            raise ValueError(f"clip_level_dbfs must be finite, got {level_dbfs!r}")
        level = 10.0 ** (level_dbfs / 20.0)
    output = np.clip(data, -level, level)
    return (
        np.asarray(output, dtype=np.float64),
        {"clip_level_dbfs": level_dbfs, "clip_level": level},
        f"hard clipping at {level_dbfs:.2f} dBFS (linear level {level:.6g})",
    )


def _inject_dropout(
    data: np.ndarray, fs: float, params: Mapping[str, Any]
) -> tuple[np.ndarray, dict[str, Any], str]:
    _check_allowed("dropout", params, {"start_s", "stop_s"})
    if "start_s" not in params or "stop_s" not in params:
        raise ValueError("dropout requires both start_s and stop_s")
    start_s = float(params["start_s"])
    stop_s = float(params["stop_s"])
    duration_s = data.size / fs
    if not (np.isfinite(start_s) and np.isfinite(stop_s)):
        raise ValueError("dropout start_s and stop_s must be finite")
    if start_s < 0.0 or stop_s > duration_s or start_s >= stop_s:
        raise ValueError(
            f"dropout requires 0 <= start_s < stop_s <= {duration_s:g}, "
            f"got start_s={start_s!r}, stop_s={stop_s!r}"
        )
    start_sample = int(round(start_s * fs))
    stop_sample = int(round(stop_s * fs))
    if stop_sample <= start_sample:
        raise ValueError("dropout interval is shorter than one sample")
    output = np.array(data, dtype=np.float64, copy=True)
    output[start_sample:stop_sample] = 0.0
    return (
        output,
        {
            "start_s": start_s,
            "stop_s": stop_s,
            "start_sample": start_sample,
            "stop_sample": stop_sample,
        },
        f"dropout ({stop_s - start_s:g} s) between {start_s:g} s and {stop_s:g} s",
    )


def _inject_dc_offset(
    data: np.ndarray, fs: float, params: Mapping[str, Any]
) -> tuple[np.ndarray, dict[str, Any], str]:
    _check_allowed("dc_offset", params, {"offset"})
    offset = float(params.get("offset", 0.05))
    if not np.isfinite(offset):
        raise ValueError(f"offset must be finite, got {params.get('offset')!r}")
    return (
        np.asarray(data + offset, dtype=np.float64),
        {"offset": offset},
        f"additive DC offset of {offset:g} (linear)",
    )


def _inject_gain_error(
    data: np.ndarray, fs: float, params: Mapping[str, Any]
) -> tuple[np.ndarray, dict[str, Any], str]:
    _check_allowed("gain_error", params, {"gain_db"})
    if "gain_db" not in params:
        raise ValueError("gain_error requires gain_db")
    gain_db = float(params["gain_db"])
    if not np.isfinite(gain_db):
        raise ValueError(f"gain_db must be finite, got {params['gain_db']!r}")
    gain = 10.0 ** (gain_db / 20.0)
    return (
        np.asarray(data * gain, dtype=np.float64),
        {"gain_db": gain_db, "gain_linear": gain},
        f"broadband gain error of {gain_db:+.2f} dB",
    )


def _inject_harmonic_distortion(
    data: np.ndarray, fs: float, params: Mapping[str, Any]
) -> tuple[np.ndarray, dict[str, Any], str]:
    _check_allowed("harmonic_distortion", params, {"percentage", "tone_hz"})
    if "percentage" not in params:
        raise ValueError("harmonic_distortion requires percentage")
    percentage = float(params["percentage"])
    if not np.isfinite(percentage) or percentage <= 0.0 or percentage >= 100.0:
        raise ValueError(f"percentage must be in (0, 100), got {params['percentage']!r}")
    if "tone_hz" in params:
        tone_hz = float(params["tone_hz"])
        if not np.isfinite(tone_hz) or tone_hz <= 0.0 or tone_hz >= fs / 2.0:
            raise ValueError(f"tone_hz must be in (0, {fs / 2.0:g}) Hz, got {tone_hz!r}")
    else:
        tone_hz = _estimate_dominant_tone(data, fs)
    tone = tone_component(data, fs, tone_hz)
    if tone.amplitude <= _AMPLITUDE_FLOOR:
        raise ValueError(f"signal has no measurable tone at {tone_hz:g} Hz")
    max_harmonic = int(np.floor((fs / 2.0) * 0.999 / tone_hz))
    multipliers = tuple(range(2, min(max_harmonic, 5) + 1))
    if len(multipliers) < 1:
        raise ValueError(
            f"tone {tone_hz:g} Hz is too high to inject harmonics below Nyquist"
        )
    weights = np.asarray([1.0 / multiplier for multiplier in multipliers], dtype=np.float64)
    weights /= np.sqrt(np.sum(np.square(weights)))
    total_amplitude = tone.amplitude * percentage / 100.0
    amplitudes = total_amplitude * weights
    time = np.arange(data.size, dtype=np.float64) / fs
    distortion = np.zeros_like(data)
    for multiplier, amplitude in zip(multipliers, amplitudes):
        distortion += amplitude * np.sin(2.0 * np.pi * multiplier * tone_hz * time)
    true_params: dict[str, Any] = {
        "percentage": percentage,
        "tone_hz": tone_hz,
        "harmonic_frequencies_hz": tuple(multiplier * tone_hz for multiplier in multipliers),
        "harmonic_amplitudes": tuple(float(value) for value in amplitudes),
        "fundamental_amplitude": tone.amplitude,
    }
    return (
        np.asarray(data + distortion, dtype=np.float64),
        true_params,
        f"harmonic distortion of {percentage:g}% added to the tone at {tone_hz:g} Hz",
    )


def _inject_latency(
    data: np.ndarray, fs: float, params: Mapping[str, Any]
) -> tuple[np.ndarray, dict[str, Any], str]:
    _check_allowed("latency", params, {"delay_ms"})
    if "delay_ms" not in params:
        raise ValueError("latency requires delay_ms")
    delay_ms = float(params["delay_ms"])
    if not np.isfinite(delay_ms) or delay_ms < 0.0:
        raise ValueError(f"delay_ms must be finite and >= 0, got {params['delay_ms']!r}")
    delay_samples = int(round(delay_ms * fs / 1000.0))
    if delay_samples >= data.size:
        raise ValueError(
            f"delay_ms={delay_ms:g} corresponds to {delay_samples} samples, "
            f"which is not shorter than the signal ({data.size} samples)"
        )
    output = np.zeros_like(data)
    if delay_samples == 0:
        output[...] = data
    else:
        output[delay_samples:] = data[:-delay_samples]
    return (
        np.asarray(output, dtype=np.float64),
        {
            "delay_ms": delay_ms,
            "delay_samples": delay_samples,
            "latency_ms_actual": 1000.0 * delay_samples / fs,
        },
        f"latency of {delay_ms:g} ms ({delay_samples} samples)",
    )


_FAULT_IMPLEMENTATIONS = {
    "clipping": _inject_clipping,
    "dropout": _inject_dropout,
    "dc_offset": _inject_dc_offset,
    "gain_error": _inject_gain_error,
    "harmonic_distortion": _inject_harmonic_distortion,
    "latency": _inject_latency,
}


def inject_fault(
    signal: ArrayLike,
    fs: float,
    fault_type: str,
    **params: Any,
) -> FaultResult:
    """Inject one deterministic fault into a signal.

    Parameters
    ----------
    signal:
        Real one-dimensional input signal.
    fs:
        Sampling rate in Hz.
    fault_type:
        One of :data:`FAULT_TYPES`: ``"clipping"``, ``"dropout"``,
        ``"dc_offset"``, ``"gain_error"``, ``"harmonic_distortion"`` or
        ``"latency"``.
    **params:
        Fault-specific parameters:

        * ``clipping``: ``clip_level_dbfs`` (default ``-6.0``) or the linear
          ``clip_level``.
        * ``dropout``: ``start_s`` and ``stop_s`` (required).
        * ``dc_offset``: ``offset`` (linear, default ``0.05``).
        * ``gain_error``: ``gain_db`` (required).
        * ``harmonic_distortion``: ``percentage`` (required) and optional
          ``tone_hz``; without ``tone_hz`` the dominant spectral peak is used.
        * ``latency``: ``delay_ms`` (required).

    Returns
    -------
    FaultResult
        Faulty output, the fault name, the true parameters and a description.

    Raises
    ------
    ValueError
        If the signal is invalid, the fault type is unknown, a required
        parameter is missing, a parameter is unknown, or a parameter value is
        out of range.

    Examples
    --------
    >>> import numpy as np
    >>> from acousticbench.dsp.signals import sine
    >>> x = sine(1000.0, 8000.0, 0.1)
    >>> result = inject_fault(x, 8000.0, "gain_error", gain_db=3.0)
    >>> result.true_params["gain_db"]
    3.0
    """
    data = as_float64_signal(signal)
    rate = validate_fs(fs)
    if fault_type not in _FAULT_IMPLEMENTATIONS:
        raise ValueError(
            f"unknown fault_type {fault_type!r}; expected one of {FAULT_TYPES}"
        )
    output, true_params, description = _FAULT_IMPLEMENTATIONS[fault_type](data, rate, params)
    logger.debug("inject_fault: type=%s params=%s", fault_type, true_params)
    return FaultResult(
        output=np.asarray(output, dtype=np.float64),
        fault_type=fault_type,
        true_params=true_params,
        description=description,
        fs=rate,
    )
