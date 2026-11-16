"""Multiband feed-forward dynamic-range compressor.

The compressor is a *virtual hearing aid* building block: a deterministic,
mono, feed-forward design with no lookahead.  The signal is split into
frequency bands with **complementary zero-phase frequency masks** (raised-cosine
crossovers on a logarithmic frequency axis), each band is level-detected, and a
static compression curve is applied per sample.

Band splitting
--------------
The virtual device processes complete, offline signals, so the bands are
produced by masking the signal's one-sided FFT with a smooth partition of
unity: every mask lies in ``[0, 1]`` and the masks sum to exactly one at every
frequency bin.  Consequently a transparent compressor (``ratio = 1``,
``makeup_db = 0``) reproduces the input to numerical precision, which makes
measured gain/compression curves unbiased.  No time-domain crossover phase
ripple is introduced.  (A real-time implementation would replace :meth:`_split`
with causal crossover filters at the cost of a non-flat band sum.)

Envelope detector
-----------------
Two one-pole low-pass filters are run on the detector signal (squared signal
for the RMS detector, absolute signal for the peak detector) — one with the
attack time constant and one with the release time constant.  The instantaneous
envelope is their maximum: fast attack on rising levels, slow release on
falling levels.  This is the classic "one-pole attack/release" approximation
and is fully deterministic and vectorised.

Static curve
------------
For an input level ``L`` (dB), threshold ``T``, ratio ``R`` and knee ``K``:

* ``L <= T - K/2``: gain reduction 0 dB,
* ``L >= T + K/2``: gain reduction ``(L - T) (1 - 1/R)``,
* otherwise a quadratic soft-knee interpolation.

The applied gain additionally includes the configured makeup gain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import scipy.signal as _signal

from acousticbench.dsp._validation import ArrayLike, as_float64_signal, validate_fs
from acousticbench.logging_utils import get_logger

__all__ = ["CompressorConfig", "MultibandCompressor"]

logger = get_logger(__name__)

#: Detector power floor (linear) avoiding ``log(0)``.
_POWER_FLOOR: float = 1e-20


@dataclass(frozen=True, slots=True)
class CompressorConfig:
    """Static and dynamic parameters of one compressor band.

    Attributes
    ----------
    threshold_dbfs:
        Compression threshold in dBFS (RMS or peak depending on ``detector``).
    ratio:
        Compression ratio (``>= 1``; 1 means no compression).
    attack_s:
        Attack time constant in seconds (> 0).
    release_s:
        Release time constant in seconds (> 0).
    knee_db:
        Soft-knee width in dB (``0`` = hard knee).
    makeup_db:
        Make-up gain added after compression in dB.
    detector:
        ``"rms"`` (level detector on the squared signal, default) or
        ``"peak"`` (level detector on the absolute signal).
    """

    threshold_dbfs: float = -35.0
    ratio: float = 3.0
    attack_s: float = 0.005
    release_s: float = 0.05
    knee_db: float = 0.0
    makeup_db: float = 0.0
    detector: str = "rms"

    def __post_init__(self) -> None:
        for name in ("threshold_dbfs", "ratio", "attack_s", "release_s", "knee_db", "makeup_db"):
            value = float(getattr(self, name))
            if not np.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")
        if self.ratio < 1.0:
            raise ValueError(f"ratio must be >= 1, got {self.ratio!r}")
        if self.attack_s <= 0.0:
            raise ValueError(f"attack_s must be > 0, got {self.attack_s!r}")
        if self.release_s <= 0.0:
            raise ValueError(f"release_s must be > 0, got {self.release_s!r}")
        if self.knee_db < 0.0:
            raise ValueError(f"knee_db must be >= 0, got {self.knee_db!r}")
        if self.detector not in ("rms", "peak"):
            raise ValueError(f"detector must be 'rms' or 'peak', got {self.detector!r}")

    def static_gain_db(self, input_level_dbfs: float | np.ndarray) -> float | np.ndarray:
        """Static compressor gain (including makeup) for an input level.

        Parameters
        ----------
        input_level_dbfs:
            Input level(s) in dBFS (scalar or array).

        Returns
        -------
        float or numpy.ndarray
            Gain in dB; scalar input gives a Python ``float``, array input an
            array.  The gain is ``<= makeup_db`` and approaches
            ``makeup_db - (L - T)(1 - 1/R)`` far above threshold.
        """
        level = np.asarray(input_level_dbfs, dtype=np.float64)
        if not np.all(np.isfinite(level)):
            raise ValueError("input_level_dbfs must be finite")
        slope = 1.0 - 1.0 / float(self.ratio)
        over = level - float(self.threshold_dbfs)
        knee = float(self.knee_db)
        if knee <= 0.0:
            reduction = np.maximum(over, 0.0) * slope
        else:
            half_knee = knee / 2.0
            reduction = np.where(
                over >= half_knee,
                over * slope,
                np.where(
                    over > -half_knee,
                    slope * np.square(over + half_knee) / (2.0 * knee),
                    0.0,
                ),
            )
        gain = float(self.makeup_db) - reduction
        if np.ndim(input_level_dbfs) == 0:
            return float(gain)
        return np.asarray(gain, dtype=np.float64)

    def gain_curve_db(self, input_levels_dbfs: np.ndarray) -> np.ndarray:
        """Vectorised static gain curve for an array of input levels."""
        return np.asarray(self.static_gain_db(input_levels_dbfs), dtype=np.float64)


def _one_pole_envelope(
    values: np.ndarray,
    fs: float,
    attack_s: float,
    release_s: float,
) -> np.ndarray:
    """One-pole attack/release envelope of a non-negative detector signal.

    Two one-pole low-pass filters are evaluated in parallel (fast attack, slow
    release) and their maximum is used.  The recursion is initialised with
    ``env[0] = (1 - a) * values[0]`` (zero state).
    """
    alpha_attack = float(np.exp(-1.0 / (attack_s * fs)))
    alpha_release = float(np.exp(-1.0 / (release_s * fs)))
    attack = _signal.lfilter([1.0 - alpha_attack], [1.0, -alpha_attack], values)
    release = _signal.lfilter([1.0 - alpha_release], [1.0, -alpha_release], values)
    return np.maximum(attack, release)


class MultibandCompressor:
    """Feed-forward multiband compressor with complementary frequency masks.

    Parameters
    ----------
    crossovers_hz:
        Ascending crossover frequencies in Hz with ``len(crossovers) + 1``
        bands.  An empty sequence creates a single full-band compressor.
    configs:
        One :class:`CompressorConfig` per band (``len(crossovers) + 1``).
    fs:
        Sampling rate in Hz.

    Examples
    --------
    >>> comp = MultibandCompressor((500.0, 2000.0), (CompressorConfig(),) * 3, 48000.0)
    >>> comp.band_edges_hz
    ((0.0, 500.0), (500.0, 2000.0), (2000.0, 24000.0))
    """

    def __init__(
        self,
        crossovers_hz: Sequence[float],
        configs: Sequence[CompressorConfig],
        fs: float,
    ) -> None:
        self._fs = validate_fs(fs)
        crossovers = tuple(float(value) for value in crossovers_hz)
        if any(not np.isfinite(value) for value in crossovers):
            raise ValueError("crossovers_hz must be finite")
        if any(value <= 0.0 for value in crossovers):
            raise ValueError("crossovers_hz must be > 0 Hz")
        if any(later <= earlier for earlier, later in zip(crossovers, crossovers[1:])):
            raise ValueError("crossovers_hz must be strictly increasing")
        if crossovers and crossovers[-1] >= self._fs / 2.0:
            raise ValueError(
                f"crossovers_hz must be below Nyquist ({self._fs / 2.0:g} Hz)"
            )
        configs_tuple = tuple(configs)
        if len(configs_tuple) != len(crossovers) + 1:
            raise ValueError(
                f"expected {len(crossovers) + 1} compressor configs for "
                f"{len(crossovers)} crossovers, got {len(configs_tuple)}"
            )
        for config in configs_tuple:
            if not isinstance(config, CompressorConfig):
                raise TypeError(
                    f"configs must contain CompressorConfig instances, got {type(config).__name__}"
                )
        self._crossovers_hz = crossovers
        self._configs = configs_tuple
        self._band_masks_cache: dict[int, tuple[np.ndarray, ...]] = {}
        logger.debug(
            "MultibandCompressor: fs=%g crossovers=%s bands=%d",
            self._fs,
            crossovers,
            len(configs_tuple),
        )

    # -- properties --------------------------------------------------------
    @property
    def fs(self) -> float:
        """Sampling rate in Hz."""
        return self._fs

    @property
    def crossovers_hz(self) -> tuple[float, ...]:
        """Crossover frequencies in Hz."""
        return self._crossovers_hz

    @property
    def configs(self) -> tuple[CompressorConfig, ...]:
        """Per-band compressor configurations."""
        return self._configs

    @property
    def n_bands(self) -> int:
        """Number of frequency bands."""
        return len(self._configs)

    @property
    def band_edges_hz(self) -> tuple[tuple[float, float], ...]:
        """Nominal band edges in Hz as ``(low, high)`` pairs."""
        edges: list[tuple[float, float]] = []
        low = 0.0
        for crossover in self._crossovers_hz:
            edges.append((low, crossover))
            low = crossover
        edges.append((low, self._fs / 2.0))
        return tuple(edges)

    # -- filter construction ----------------------------------------------
    def _band_masks(self, n_samples: int) -> tuple[np.ndarray, ...]:
        """Complementary one-sided band masks for a record of ``n_samples``."""
        cached = self._band_masks_cache.get(n_samples)
        if cached is not None:
            return cached
        frequencies = np.fft.rfftfreq(n_samples, d=1.0 / self._fs)
        n_bands = self.n_bands
        if n_bands == 1:
            masks = (np.ones(frequencies.size, dtype=np.float64),)
        else:
            # One-third-octave raised-cosine transition around each crossover.
            transition_ratio = 2.0 ** (1.0 / 6.0)
            log_ratio = float(np.log(transition_ratio))

            def lowpass(crossover: float) -> np.ndarray:
                mask = np.ones_like(frequencies)
                mask[frequencies >= crossover * transition_ratio] = 0.0
                inner = (frequencies > crossover / transition_ratio) & (
                    frequencies < crossover * transition_ratio
                )
                position = (np.log(frequencies[inner] / crossover) / log_ratio + 1.0) / 2.0
                mask[inner] = 0.5 * (1.0 + np.cos(np.pi * position))
                return mask

            lowpass_by_crossover = [lowpass(value) for value in self._crossovers_hz]
            masks_list: list[np.ndarray] = []
            for band_index in range(n_bands):
                mask = np.ones_like(frequencies)
                if band_index > 0:
                    mask = mask * (1.0 - lowpass_by_crossover[band_index - 1])
                if band_index < len(self._crossovers_hz):
                    mask = mask * lowpass_by_crossover[band_index]
                masks_list.append(mask)
            total = np.sum(masks_list, axis=0)
            if np.any(total <= 0.0):  # pragma: no cover - masks are positive
                raise ValueError("band masks do not cover the frequency axis")
            masks = tuple(np.asarray(mask / total, dtype=np.float64) for mask in masks_list)
        self._band_masks_cache[n_samples] = masks
        return masks

    def _split(self, signal: np.ndarray) -> tuple[np.ndarray, ...]:
        """Split a signal into complementary zero-phase band signals."""
        n = signal.size
        masks = self._band_masks(n)
        spectrum = np.fft.rfft(signal)
        return tuple(
            np.asarray(np.fft.irfft(spectrum * mask, n=n), dtype=np.float64)
            for mask in masks
        )

    # -- processing --------------------------------------------------------
    def _band_gain_db(self, band: np.ndarray, config: CompressorConfig) -> np.ndarray:
        """Per-sample compressor gain in dB for one band signal."""
        if config.detector == "rms":
            detector_values = np.square(band)
            envelope = _one_pole_envelope(
                detector_values, self._fs, config.attack_s, config.release_s
            )
            level_db = 10.0 * np.log10(np.maximum(envelope, _POWER_FLOOR))
        else:
            detector_values = np.abs(band)
            envelope = _one_pole_envelope(
                detector_values, self._fs, config.attack_s, config.release_s
            )
            level_db = 20.0 * np.log10(np.maximum(envelope, _POWER_FLOOR))
        return config.gain_curve_db(level_db)

    def process(self, signal: ArrayLike) -> np.ndarray:
        """Compress a mono signal.

        Parameters
        ----------
        signal:
            Real one-dimensional input signal.

        Returns
        -------
        numpy.ndarray
            Compressed ``float64`` signal of the same length.

        Raises
        ------
        ValueError
            If the signal is invalid.  A silent signal is passed through
            unchanged (all gains reduce to the makeup gain).
        """
        data = as_float64_signal(signal)
        bands = self._split(data)
        output = np.zeros_like(data)
        for band, config in zip(bands, self._configs):
            gain_db = self._band_gain_db(band, config)
            output += band * np.power(10.0, gain_db / 20.0)
        return np.asarray(output, dtype=np.float64)

    def static_gain_db(self, input_level_dbfs: float | np.ndarray) -> tuple[float, ...]:
        """Static per-band gain for a common input level.

        Parameters
        ----------
        input_level_dbfs:
            Assumed input level in dBFS (scalar).

        Returns
        -------
        tuple of float
            One gain in dB per band, in ascending frequency order.  For a
            single-band compressor the tuple has length one; use
            :meth:`CompressorConfig.static_gain_db` for a scalar gain curve.
        """
        return tuple(float(config.static_gain_db(input_level_dbfs)) for config in self._configs)
