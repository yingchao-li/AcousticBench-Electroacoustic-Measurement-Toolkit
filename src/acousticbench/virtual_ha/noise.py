"""Sensor-noise helpers for virtual hearing-aid simulations.

These are thin, documented wrappers around
:mod:`acousticbench.dsp.signals` that add the two levels of sensor-noise
modelling needed by the virtual device: noise with a prescribed absolute RMS
level and noise with a prescribed SNR relative to the signal.
"""

from __future__ import annotations

import numpy as np

from acousticbench.dsp._validation import ArrayLike, as_float64_signal
from acousticbench.dsp.signals import pink_noise, rms, white_noise
from acousticbench.logging_utils import get_logger

__all__ = ["NOISE_COLORS", "add_sensor_noise", "sensor_noise"]

logger = get_logger(__name__)

#: Supported sensor-noise colours.
NOISE_COLORS: tuple[str, ...] = ("white", "pink")


def _validate_color(color: str) -> str:
    """Validate a noise colour name."""
    if color not in NOISE_COLORS:
        raise ValueError(f"color must be one of {NOISE_COLORS}, got {color!r}")
    return color


def sensor_noise(
    n_samples: int,
    level_dbfs: float,
    seed: int | None = None,
    color: str = "white",
) -> np.ndarray:
    """Generate sensor noise at an absolute RMS level.

    Parameters
    ----------
    n_samples:
        Number of samples.
    level_dbfs:
        RMS level of the noise in dBFS.
    seed:
        Seed for the random generator.
    color:
        ``"white"`` or ``"pink"``.

    Returns
    -------
    numpy.ndarray
        ``float64`` noise signal.
    """
    _validate_color(color)
    logger.debug("sensor_noise: n=%d level_dbfs=%g color=%s", n_samples, level_dbfs, color)
    generator = white_noise if color == "white" else pink_noise
    return np.asarray(generator(n_samples, seed=seed, level_dbfs=level_dbfs), dtype=np.float64)


def add_sensor_noise(
    signal: ArrayLike,
    *,
    snr_db: float | None = None,
    level_dbfs: float | None = None,
    seed: int | None = None,
    color: str = "white",
) -> np.ndarray:
    """Add sensor noise to a signal, specified by SNR or by absolute level.

    Exactly one of ``snr_db`` and ``level_dbfs`` must be given.

    Parameters
    ----------
    signal:
        Input signal.
    snr_db:
        If given, the noise RMS is ``rms(signal) / 10 ** (snr_db / 20)``.
    level_dbfs:
        If given, the noise RMS is ``10 ** (level_dbfs / 20)``.
    seed:
        Seed for the random generator.
    color:
        ``"white"`` or ``"pink"``.

    Returns
    -------
    numpy.ndarray
        ``signal + noise`` as ``float64``.

    Raises
    ------
    ValueError
        If neither or both of ``snr_db`` / ``level_dbfs`` are given, the
        colour is unknown, or the signal is silent when ``snr_db`` is used.
    """
    data = as_float64_signal(signal)
    _validate_color(color)
    if (snr_db is None) == (level_dbfs is None):
        raise ValueError("exactly one of snr_db or level_dbfs must be specified")
    if level_dbfs is not None:
        noise = sensor_noise(data.size, float(level_dbfs), seed=seed, color=color)
    else:
        signal_rms = rms(data)
        if signal_rms <= 0.0:
            raise ValueError("cannot add noise to a silent signal; SNR is undefined")
        target_rms = signal_rms / 10.0 ** (float(snr_db) / 20.0)
        noise = sensor_noise(data.size, 20.0 * np.log10(target_rms), seed=seed, color=color)
    return np.asarray(data + noise, dtype=np.float64)
