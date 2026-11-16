"""Deterministic signal generators and level helpers.

Level conventions
-----------------
All levels are expressed in **dBFS** relative to a full-scale signal of unit
peak amplitude.  The RMS level of a signal ``x`` is ``dbfs(x) = 20 log10(rms(x))``,
so a full-scale sine (peak amplitude 1.0) has an RMS level of
``20 log10(1 / sqrt(2)) = -3.01 dBFS``.  Consequently a ``level_dbfs``
argument of ``-20`` denotes a signal whose RMS value is ``10 ** (-1) = 0.1``.

Every generator returns a contiguous ``float64`` :class:`numpy.ndarray` and is
reproducible from the integer ``seed`` via :func:`numpy.random.default_rng`.
"""

from __future__ import annotations

import numpy as np

from acousticbench.dsp._validation import (
    ArrayLike,
    as_float64_signal,
    validate_frequency,
    validate_fs,
    validate_positive,
    validate_sample_count,
)
from acousticbench.logging_utils import get_logger

__all__ = [
    "add_awgn",
    "apply_gain_db",
    "dbfs",
    "log_sweep",
    "multi_tone",
    "pink_noise",
    "rms",
    "sine",
    "white_noise",
]

logger = get_logger(__name__)

#: Smallest non-zero level used to avoid ``log(0)``; well below any realistic
#: measurement floor but still representable as a float.
_LEVEL_FLOOR_RMS: float = 1e-12


def _n_samples(fs: float, duration_s: float) -> int:
    """Round ``fs * duration_s`` to an integer number of samples (>= 1)."""
    n = int(round(validate_fs(fs) * validate_positive(duration_s, "duration_s")))
    if n < 1:
        raise ValueError("duration_s is too short for the given sampling rate")
    return n


def _scaled_noise(noise: np.ndarray, level_dbfs: float | None) -> np.ndarray:
    """Scale ``noise`` to unit RMS (or to ``level_dbfs`` RMS) and return it."""
    unit = noise / rms(noise)
    if level_dbfs is None:
        return unit
    target = float(level_dbfs)
    if not np.isfinite(target):
        raise ValueError(f"level_dbfs must be finite, got {level_dbfs!r}")
    return unit * 10.0 ** (target / 20.0)


def sine(
    freq_hz: float,
    fs: float,
    duration_s: float,
    amplitude: float = 1.0,
    phase_rad: float = 0.0,
) -> np.ndarray:
    """Generate a real sine tone.

    Parameters
    ----------
    freq_hz:
        Tone frequency in Hz; must be inside ``(0, fs / 2)``.
    fs:
        Sampling rate in Hz.
    duration_s:
        Signal duration in seconds.
    amplitude:
        Peak amplitude (linear, not dBFS).
    phase_rad:
        Initial phase in radians at ``t = 0``.

    Returns
    -------
    numpy.ndarray
        ``float64`` sine signal of length ``round(fs * duration_s)``.

    Examples
    --------
    >>> x = sine(1000.0, 48000.0, 0.01)
    >>> x.dtype
    dtype('float64')
    """
    rate = validate_fs(fs)
    freq = validate_frequency(freq_hz, rate)
    amp = float(amplitude)
    if not np.isfinite(amp):
        raise ValueError(f"amplitude must be finite, got {amplitude!r}")
    n = _n_samples(rate, duration_s)
    time = np.arange(n, dtype=np.float64) / rate
    return np.asarray(amp * np.sin(2.0 * np.pi * freq * time + float(phase_rad)), dtype=np.float64)


def multi_tone(
    freqs_hz: ArrayLike,
    fs: float,
    duration_s: float,
    amplitudes: ArrayLike | None = None,
) -> np.ndarray:
    """Sum of one or more sine tones with zero initial phase.

    Parameters
    ----------
    freqs_hz:
        Tone frequencies in Hz (each inside ``(0, fs / 2)``).
    fs:
        Sampling rate in Hz.
    duration_s:
        Signal duration in seconds.
    amplitudes:
        Optional peak amplitudes, one per frequency.  Defaults to 1.0 for all.

    Returns
    -------
    numpy.ndarray
        ``float64`` multi-tone signal.
    """
    rate = validate_fs(fs)
    frequencies = np.atleast_1d(np.asarray(freqs_hz, dtype=np.float64))
    if frequencies.ndim != 1 or frequencies.size == 0:
        raise ValueError("freqs_hz must be a non-empty one-dimensional sequence")
    frequencies = np.asarray(
        [validate_frequency(f, rate, "freqs_hz") for f in frequencies], dtype=np.float64
    )
    if amplitudes is None:
        gains = np.ones_like(frequencies)
    else:
        gains = np.atleast_1d(np.asarray(amplitudes, dtype=np.float64))
        if gains.shape != frequencies.shape:
            raise ValueError(
                f"amplitudes must have shape {frequencies.shape}, got {gains.shape}"
            )
        if not np.all(np.isfinite(gains)):
            raise ValueError("amplitudes must all be finite")
    n = _n_samples(rate, duration_s)
    time = np.arange(n, dtype=np.float64) / rate
    tones = np.sin(2.0 * np.pi * np.outer(frequencies, time))
    return np.asarray(gains @ tones, dtype=np.float64)


def white_noise(
    n_samples: int,
    seed: int | None = None,
    level_dbfs: float | None = None,
) -> np.ndarray:
    """Generate white Gaussian noise with unit (or requested) RMS level.

    Parameters
    ----------
    n_samples:
        Number of samples.
    seed:
        Seed for :func:`numpy.random.default_rng`.
    level_dbfs:
        Optional RMS level in dBFS.  ``None`` yields exact unit RMS.

    Returns
    -------
    numpy.ndarray
        ``float64`` white noise signal.
    """
    count = validate_sample_count(n_samples)
    rng = np.random.default_rng(seed)
    return _scaled_noise(rng.standard_normal(count), level_dbfs)


def pink_noise(
    n_samples: int,
    seed: int | None = None,
    level_dbfs: float | None = None,
) -> np.ndarray:
    """Generate pink (``1 / f`` power) noise with unit (or requested) RMS level.

    The noise is synthesised by shaping white noise in the frequency domain
    with ``1 / sqrt(f)`` amplitude weights, zeroing the DC bin and removing the
    residual mean.  The result therefore has equal energy per octave.

    Parameters
    ----------
    n_samples:
        Number of samples (>= 2).
    seed:
        Seed for :func:`numpy.random.default_rng`.
    level_dbfs:
        Optional RMS level in dBFS.  ``None`` yields exact unit RMS.

    Returns
    -------
    numpy.ndarray
        ``float64`` pink noise signal.
    """
    count = validate_sample_count(n_samples, minimum=2)
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(count)
    freqs = np.fft.rfftfreq(count)
    shaping = np.zeros_like(freqs)
    shaping[1:] = 1.0 / np.sqrt(freqs[1:])
    spectrum = np.fft.rfft(white) * shaping
    pink = np.fft.irfft(spectrum, n=count)
    pink -= pink.mean()
    return _scaled_noise(pink, level_dbfs)


def log_sweep(
    f_start_hz: float,
    f_end_hz: float,
    duration_s: float,
    fs: float,
    amplitude: float = 1.0,
) -> np.ndarray:
    """Generate an exponential (logarithmic) sine sweep.

    The instantaneous frequency increases exponentially from ``f_start_hz`` to
    ``f_end_hz`` over ``duration_s``:

    .. math::

        f(t) = f_1 \\exp\\left(\\frac{t}{L}\\right), \\quad
        L = \\frac{T}{\\ln(f_2 / f_1)}

    and the signal is ``amplitude * sin(2 pi f1 L (exp(t / L) - 1))``.

    Parameters
    ----------
    f_start_hz:
        Start frequency in Hz (> 0).
    f_end_hz:
        End frequency in Hz (> ``f_start_hz`` and below Nyquist).
    duration_s:
        Sweep duration in seconds.
    fs:
        Sampling rate in Hz.
    amplitude:
        Peak amplitude (linear).

    Returns
    -------
    numpy.ndarray
        ``float64`` sweep signal.
    """
    rate = validate_fs(fs)
    f_start = validate_frequency(f_start_hz, rate, "f_start_hz")
    f_end = validate_frequency(f_end_hz, rate, "f_end_hz")
    if f_end <= f_start:
        raise ValueError(f"f_end_hz must be > f_start_hz, got {f_start!r} -> {f_end!r}")
    amp = float(amplitude)
    if not np.isfinite(amp):
        raise ValueError(f"amplitude must be finite, got {amplitude!r}")
    duration = validate_positive(duration_s, "duration_s")
    n = _n_samples(rate, duration)
    time = np.arange(n, dtype=np.float64) / rate
    time_constant = duration / np.log(f_end / f_start)
    phase = 2.0 * np.pi * f_start * time_constant * (np.exp(time / time_constant) - 1.0)
    return np.asarray(amp * np.sin(phase), dtype=np.float64)


def add_awgn(
    signal: ArrayLike,
    snr_db: float,
    seed: int | None = None,
) -> np.ndarray:
    """Add white Gaussian noise at a prescribed signal-to-noise ratio.

    The noise RMS is set to ``rms(signal) / 10 ** (snr_db / 20)``, so the
    returned signal has the requested in-band SNR exactly in expectation.

    Parameters
    ----------
    signal:
        Input signal.
    snr_db:
        Signal-to-noise ratio in dB (may be negative).
    seed:
        Seed for the noise generator.

    Returns
    -------
    numpy.ndarray
        ``signal + noise`` as ``float64``.

    Raises
    ------
    ValueError
        If the input is invalid, ``snr_db`` is not finite, or the signal is
        digital silence (for which SNR is undefined).
    """
    data = as_float64_signal(signal)
    snr = float(snr_db)
    if not np.isfinite(snr):
        raise ValueError(f"snr_db must be finite, got {snr_db!r}")
    signal_rms = rms(data)
    if signal_rms <= 0.0:
        raise ValueError("cannot add noise to a silent signal; SNR is undefined")
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(data.size) * (signal_rms / 10.0 ** (snr / 20.0))
    return np.asarray(data + noise, dtype=np.float64)


def rms(signal: ArrayLike) -> float:
    """Root-mean-square value of a real signal.

    Parameters
    ----------
    signal:
        One-dimensional real signal.

    Returns
    -------
    float
        ``sqrt(mean(signal ** 2))``.
    """
    data = as_float64_signal(signal)
    return float(np.sqrt(np.mean(np.square(data))))


def dbfs(signal: ArrayLike) -> float:
    """RMS level of a signal in dBFS.

    Parameters
    ----------
    signal:
        One-dimensional real signal.

    Returns
    -------
    float
        ``20 log10(rms(signal))``; digital silence yields ``-inf``.
    """
    level = rms(signal)
    if level <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(level))


def apply_gain_db(signal: ArrayLike, gain_db: float) -> np.ndarray:
    """Apply a broadband gain in dB.

    Parameters
    ----------
    signal:
        Input signal.
    gain_db:
        Gain in dB (positive = amplification).

    Returns
    -------
    numpy.ndarray
        ``signal * 10 ** (gain_db / 20)`` as ``float64``.
    """
    data = as_float64_signal(signal)
    gain = float(gain_db)
    if not np.isfinite(gain):
        raise ValueError(f"gain_db must be finite, got {gain_db!r}")
    return np.asarray(data * 10.0 ** (gain / 20.0), dtype=np.float64)
