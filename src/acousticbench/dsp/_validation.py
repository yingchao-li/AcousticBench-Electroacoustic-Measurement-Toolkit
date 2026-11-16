"""Internal input-validation helpers shared by the DSP modules.

The public API accepts "array-like" inputs (lists, tuples, integer arrays) but
all downstream computations are performed on contiguous ``float64`` arrays.
Invalid values are rejected eagerly with :class:`ValueError` so that a
physically meaningless result can never be produced silently.
"""

from __future__ import annotations

from typing import TypeAlias

import numpy as np

__all__ = [
    "ArrayLike",
    "as_float64_signal",
    "validate_frequency",
    "validate_fs",
    "validate_positive",
    "validate_sample_count",
]

ArrayLike: TypeAlias = np.ndarray | list[float] | tuple[float, ...]


def validate_fs(fs: float) -> float:
    """Return ``fs`` as a positive finite sampling rate in Hz.

    Parameters
    ----------
    fs:
        Sampling rate in Hz.

    Returns
    -------
    float
        The validated sampling rate.

    Raises
    ------
    ValueError
        If ``fs`` is not finite or not strictly positive.
    """
    fs_value = float(fs)
    if not np.isfinite(fs_value) or fs_value <= 0.0:
        raise ValueError(f"sampling rate fs must be finite and > 0 Hz, got {fs!r}")
    return fs_value


def validate_positive(value: float, name: str) -> float:
    """Return ``value`` as a positive finite float, raising otherwise."""
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and > 0, got {value!r}")
    return result


def validate_sample_count(n_samples: int, *, minimum: int = 1) -> int:
    """Return ``n_samples`` as an integer ``>= minimum``."""
    if isinstance(n_samples, bool) or not isinstance(n_samples, (int, np.integer)):
        raise ValueError(f"n_samples must be an integer, got {type(n_samples).__name__}")
    count = int(n_samples)
    if count < minimum:
        raise ValueError(f"n_samples must be >= {minimum}, got {count}")
    return count


def validate_frequency(freq_hz: float, fs: float, name: str = "frequency_hz") -> float:
    """Validate a frequency that must lie strictly inside ``(0, fs / 2)``."""
    freq = float(freq_hz)
    if not np.isfinite(freq) or freq <= 0.0:
        raise ValueError(f"{name} must be finite and > 0 Hz, got {freq_hz!r}")
    if freq >= fs / 2.0:
        raise ValueError(f"{name} must be below Nyquist ({fs / 2.0:g} Hz), got {freq:g} Hz")
    return freq


def as_float64_signal(
    signal: ArrayLike,
    name: str = "signal",
    *,
    min_length: int = 1,
) -> np.ndarray:
    """Convert ``signal`` to a contiguous one-dimensional ``float64`` array.

    Parameters
    ----------
    signal:
        One-dimensional array-like signal.
    name:
        Name used in error messages.
    min_length:
        Minimum required number of samples.

    Returns
    -------
    numpy.ndarray
        Contiguous ``float64`` copy of the input.

    Raises
    ------
    ValueError
        If the signal is not one-dimensional, too short or contains
        non-finite values.  Non-finite samples are never silently replaced.
    """
    array = np.asarray(signal, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional, got shape {array.shape}")
    if array.size < min_length:
        raise ValueError(f"{name} must contain at least {min_length} sample(s), got {array.size}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains non-finite values")
    return np.ascontiguousarray(array)
