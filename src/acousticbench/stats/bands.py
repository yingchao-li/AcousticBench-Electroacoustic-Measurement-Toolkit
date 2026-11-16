"""Frequency-band definitions and aggregation helpers.

Bands are defined by nominal centre frequencies with the standard octave /
one-third-octave edge ratios.  Aggregation over DFT bins uses a power average,
which is the appropriate operation for transfer-function levels; the result is
identical for ratios (e.g. insertion gain) regardless of the arbitrary
free-field scaling of the stored loudspeaker data.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Sequence

import numpy as np

from acousticbench.exceptions import ConfigurationError
from acousticbench.types import NYQUIST_HZ

__all__ = [
    "Band",
    "bands_from_config",
    "band_mask",
    "custom_bands",
    "octave_bands",
    "third_octave_bands",
]

#: Nominal octave-band centre frequencies (IEC 61260 preferred numbers).
OCTAVE_CENTERS: tuple[float, ...] = (
    31.5, 63.0, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0
)

#: Nominal one-third-octave-band centre frequencies.
THIRD_OCTAVE_CENTERS: tuple[float, ...] = (
    25.0, 31.5, 40.0, 50.0, 63.0, 80.0, 100.0, 125.0, 160.0, 200.0, 250.0,
    315.0, 400.0, 500.0, 630.0, 800.0, 1000.0, 1250.0, 1600.0, 2000.0, 2500.0,
    3150.0, 4000.0, 5000.0, 6300.0, 8000.0, 10000.0, 12500.0, 16000.0, 20000.0,
)


@dataclass(frozen=True, slots=True)
class Band:
    """A frequency band with nominal centre and edges."""

    label: str
    center_hz: float
    low_hz: float
    high_hz: float

    def contains(self, frequencies_hz: np.ndarray) -> np.ndarray:
        freq = np.asarray(frequencies_hz)
        return (freq >= self.low_hz) & (freq < self.high_hz)


def _bands_from_centers(
    centers: Iterable[float],
    *,
    f_min: float = 20.0,
    f_max: float = NYQUIST_HZ,
    ratio: float,
    label_fmt: str,
) -> tuple[Band, ...]:
    bands: list[Band] = []
    for center in centers:
        low = max(center / ratio, f_min)
        high = min(center * ratio, f_max)
        if low >= high:
            continue
        bands.append(
            Band(
                label=label_fmt.format(center=center),
                center_hz=float(center),
                low_hz=float(low),
                high_hz=float(high),
            )
        )
    return tuple(bands)


def octave_bands(
    f_min: float = 50.0,
    f_max: float = NYQUIST_HZ,
    centers: Sequence[float] | None = None,
) -> tuple[Band, ...]:
    """Return octave bands (default: 50 Hz … Nyquist, limited to the data range)."""
    return _bands_from_centers(
        centers or OCTAVE_CENTERS,
        f_min=f_min,
        f_max=f_max,
        ratio=sqrt(2.0),
        label_fmt="{center:g} Hz",
    )


def third_octave_bands(
    f_min: float = 50.0,
    f_max: float = NYQUIST_HZ,
    centers: Sequence[float] | None = None,
) -> tuple[Band, ...]:
    """Return one-third-octave bands (default: ≥ 50 Hz)."""
    return _bands_from_centers(
        centers or THIRD_OCTAVE_CENTERS,
        f_min=f_min,
        f_max=f_max,
        ratio=2.0 ** (1.0 / 6.0),
        label_fmt="{center:g} Hz",
    )


def custom_bands(edges_hz: Sequence[float]) -> tuple[Band, ...]:
    """Build bands from explicit ascending edges (length ≥ 2)."""
    edges = np.asarray(edges_hz, dtype=float)
    if edges.ndim != 1 or edges.size < 2:
        raise ConfigurationError("custom band edges must be a 1-D sequence with ≥ 2 entries")
    if np.any(np.diff(edges) <= 0):
        raise ConfigurationError("custom band edges must be strictly increasing")
    bands = []
    for low, high in zip(edges[:-1], edges[1:]):
        center = sqrt(low * high) if low > 0 else high / sqrt(2.0)
        bands.append(
            Band(
                label=f"{low:g}–{high:g} Hz",
                center_hz=float(center),
                low_hz=float(low),
                high_hz=float(high),
            )
        )
    return tuple(bands)


def bands_from_config(config) -> tuple[Band, ...]:  # noqa: ANN001 - avoids circular import
    """Return the configured band set (octave, third-octave or custom)."""
    method = config.analysis.bands.method.lower()
    custom = config.analysis.bands.custom_edges_hz
    if method in {"octave", "oct"}:
        return octave_bands()
    if method in {"third_octave", "third-octave", "third"}:
        return third_octave_bands()
    if method in {"custom", "explicit"}:
        if not custom:
            raise ConfigurationError(
                "analysis.bands.custom_edges_hz must be set when bands.method='custom'"
            )
        return custom_bands(custom)
    raise ConfigurationError(
        f"Unknown band method {method!r}; expected 'octave', 'third_octave' or 'custom'"
    )


def band_mask(frequencies_hz: np.ndarray, band: Band) -> np.ndarray:
    """Boolean mask of the DFT bins that belong to ``band``."""
    return band.contains(np.asarray(frequencies_hz))
