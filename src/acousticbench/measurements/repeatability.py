"""Reinsertion repeatability of real-ear measurements.

The study measured every earpiece three times (three reinsertions).  These are
technical repeats: the subject is the independent unit and the reinsertions
quantify measurement repeatability, not between-subject variability.

Definitions used here
---------------------
*Per-frequency repeatability* (:func:`reinsertion_sd_by_frequency`)
    For every (device, subject, frequency) the sample standard deviation
    (``ddof=1``) and the range of the available reinsertions.  Both are NaN
    when fewer than two valid reinsertions exist; nothing is imputed.
*Band repeatability* (:func:`repeatability_summary`)
    Band levels are computed first (power average across DFT bins for complex
    transfer cubes via :meth:`TransferCube.band_levels`; arithmetic mean of the
    dB values for cubes that already are level cubes).  Then, per subject, the
    standard deviation across reinsertions is computed; per (device, band) the
    median and 95th percentile of these within-subject SDs are reported, as is
    the repeatability coefficient ``1.96 * sqrt(2) * SD`` (the 95 % limit of
    the difference between two reinsertions) and ICC(2,1) across reinsertions.
*Device summary* (:func:`repeatability_by_device`)
    The same table aggregated over one band, by default 500–4000 Hz (the
    primary band of the analysis configuration, hard-coded here as required by
    the API so the measurement function is configuration-independent).
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from acousticbench.data.dataset import TransferCube
from acousticbench.exceptions import MeasurementError
from acousticbench.logging_utils import get_logger
from acousticbench.stats.bands import Band
from acousticbench.stats.icc import icc_2_1

__all__ = [
    "repeatability_by_device",
    "repeatability_summary",
    "reinsertion_sd_by_frequency",
    "extract_levels",
]

logger = get_logger(__name__)

#: Default aggregation band of :func:`repeatability_by_device` (Hz).
DEFAULT_BAND_HZ: tuple[float, float] = (500.0, 4000.0)

_SUMMARY_COLUMNS = (
    "band",
    "band_center_hz",
    "device_code",
    "device",
    "family",
    "coupling",
    "condition",
    "n_subjects",
    "median_level_db",
    "sd_reinsertion_db_median",
    "sd_reinsertion_db_p95",
    "repeatability_coefficient_db",
    "icc_2_1",
)


def extract_levels(cube: TransferCube, reference: float = 1.0) -> np.ndarray:
    """Return the dB level array of a cube with NaN for invalid entries.

    Parameters
    ----------
    cube:
        A :class:`~acousticbench.data.dataset.TransferCube`.  Complex transfer
        cubes are converted with ``20 log10(|value| / reference)``; cubes that
        already store levels (``kind="level_db"`` / ``"threshold_dbv"``) are
        returned unchanged.
    reference:
        Reference value of the dB conversion (default 1.0 Pa).

    Returns
    -------
    numpy.ndarray
        Float array of shape ``(n_freq, n_device, n_subject, n_reinsertion)``
        with NaN for invalid entries.
    """
    if not isinstance(cube, TransferCube):
        raise TypeError(f"cube must be a TransferCube, got {type(cube).__name__}")
    if not np.isfinite(float(reference)) or float(reference) <= 0.0:
        raise ValueError(f"reference must be a positive finite value, got {reference!r}")
    levels = cube.level_array(reference=float(reference))
    if levels.ndim != 4:
        raise MeasurementError(
            f"expected a 4-D (frequency, device, subject, reinsertion) array, got {levels.shape}"
        )
    return levels


def _band_level_frame(
    cube: TransferCube,
    bands: Sequence[Band],
    reference: float,
) -> pd.DataFrame:
    """Band levels of a cube as a tidy DataFrame (internal helper).

    Complex transfer cubes are aggregated with a power average via
    :meth:`TransferCube.band_levels` (the physically correct operation).  For
    cubes that are already level cubes (``kind="level_db"`` /
    ``"threshold_dbv"``) an arithmetic mean of the dB values inside the band is
    used; this is documented as an acceptable approximation for averaging
    already-logarithmic band levels.
    """
    band_list = tuple(bands)
    if not band_list:
        raise ValueError("bands must not be empty")
    if cube.kind == "transfer":
        return cube.band_levels(band_list, reference=reference)

    levels = extract_levels(cube, reference)
    n_freq, n_dev, n_subj, n_re = levels.shape
    frames: list[pd.DataFrame] = []
    for band in band_list:
        mask = band.contains(cube.freq_hz)
        if not mask.any():
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            mean_level = np.nanmean(levels[mask], axis=0)  # (device, subject, reinsertion)
        counted = np.isfinite(levels[mask]).sum(axis=0)
        mean_level = np.where(counted > 0, mean_level, np.nan)
        device_codes = np.repeat([d.code for d in cube.devices], n_subj * n_re)
        device_parts = np.repeat([d.label for d in cube.devices], n_subj * n_re)
        family_parts = np.repeat([d.family for d in cube.devices], n_subj * n_re)
        family_label_parts = np.repeat([d.family_label for d in cube.devices], n_subj * n_re)
        coupling_parts = np.repeat([d.coupling.value for d in cube.devices], n_subj * n_re)
        condition_parts = np.repeat(
            [d.condition.value if d.condition else None for d in cube.devices], n_subj * n_re
        )
        frames.append(
            pd.DataFrame(
                {
                    "band": band.label,
                    "band_center_hz": float(band.center_hz),
                    "band_low_hz": float(band.low_hz),
                    "band_high_hz": float(band.high_hz),
                    "device_code": device_codes,
                    "device": device_parts,
                    "family": family_parts,
                    "family_label": family_label_parts,
                    "coupling": coupling_parts,
                    "condition": condition_parts,
                    "subject": np.tile(np.repeat(cube.subjects, n_re), n_dev),
                    "reinsertion": np.tile(cube.reinsertions, n_dev * n_subj),
                    "level_db": np.asarray(mean_level, dtype=float).reshape(-1),
                    "valid": np.isfinite(mean_level).reshape(-1),
                }
            )
        )
    if not frames:
        raise MeasurementError(
            "No configured frequency band overlaps the cube's frequency axis"
        )
    return pd.concat(frames, ignore_index=True)


def reinsertion_sd_by_frequency(
    cube: TransferCube,
    *,
    reference: float = 1.0,
) -> pd.DataFrame:
    """Reinsertion SD and range per device, subject and frequency.

    Parameters
    ----------
    cube:
        Measurement cube (complex transfer or level cube).
    reference:
        Reference of the dB conversion.

    Returns
    -------
    pandas.DataFrame
        Tidy long frame with one row per (device, subject, frequency):

        ``frequency_hz, device_code, device, family, coupling, condition,
        subject, n_reinsertions, sd_db, range_db``

        ``sd_db`` is the sample SD (``ddof=1``) across the valid reinsertions
        and ``range_db`` their max-minus-min.  Both are NaN when fewer than two
        valid reinsertions exist.
    """
    levels = extract_levels(cube, reference)
    n_freq, n_dev, n_subj, _ = levels.shape
    finite = np.isfinite(levels)
    n_valid = finite.sum(axis=3)
    with warnings.catch_warnings(), np.errstate(invalid="ignore"):
        warnings.simplefilter("ignore", category=RuntimeWarning)
        sd = np.nanstd(levels, axis=3, ddof=1)
        spread = np.nanmax(levels, axis=3) - np.nanmin(levels, axis=3)
    enough = n_valid >= 2
    sd = np.where(enough, sd, np.nan)
    spread = np.where(enough, spread, np.nan)

    frames: list[pd.DataFrame] = []
    for device_index, device in enumerate(cube.devices):
        frames.append(
            pd.DataFrame(
                {
                    "frequency_hz": np.tile(cube.freq_hz, n_subj),
                    "device_code": device.code,
                    "device": device.label,
                    "family": device.family,
                    "coupling": device.coupling.value,
                    "condition": device.condition.value if device.condition else None,
                    "subject": np.repeat(cube.subjects, n_freq),
                    "n_reinsertions": n_valid[:, device_index, :].reshape(-1, order="F"),
                    "sd_db": sd[:, device_index, :].reshape(-1, order="F"),
                    "range_db": spread[:, device_index, :].reshape(-1, order="F"),
                }
            )
        )
    frame = pd.concat(frames, ignore_index=True)
    logger.debug(
        "reinsertion_sd_by_frequency: %d rows from cube %r", len(frame), cube.name
    )
    return frame


def _band_matrix(frame: pd.DataFrame, *, band: Band, device_code: int) -> np.ndarray | None:
    """Pivot one (band, device) slice into a subjects × reinsertions matrix."""
    subset = frame.loc[
        (frame["band"] == band.label) & (frame["device_code"] == device_code),
        ["subject", "reinsertion", "level_db"],
    ]
    if subset.empty:
        return None
    matrix = subset.pivot(index="subject", columns="reinsertion", values="level_db")
    return matrix.to_numpy(dtype=float)


def _summarise_matrix(matrix: np.ndarray) -> dict[str, float]:
    """Repeatability statistics of a subjects × reinsertions band matrix."""
    counts = np.isfinite(matrix).sum(axis=1)
    with warnings.catch_warnings(), np.errstate(invalid="ignore"):
        warnings.simplefilter("ignore", category=RuntimeWarning)
        subject_means = np.nanmean(matrix, axis=1)
        within_sd = np.nanstd(matrix, axis=1, ddof=1)
    within_sd = np.where(counts >= 2, within_sd, np.nan)
    usable = counts >= 2
    n_subjects = int(usable.sum())
    if n_subjects == 0:
        return {
            "n_subjects": 0,
            "median_level_db": float("nan"),
            "sd_reinsertion_db_median": float("nan"),
            "sd_reinsertion_db_p95": float("nan"),
            "repeatability_coefficient_db": float("nan"),
            "icc_2_1": float("nan"),
        }
    usable_sd = within_sd[usable]
    sd_median = float(np.nanmedian(usable_sd))
    sd_p95 = float(np.nanpercentile(usable_sd, 95.0))
    try:
        icc = float(icc_2_1(matrix).icc)
    except ValueError as exc:
        logger.debug("ICC(2,1) not computable for this band/device: %s", exc)
        icc = float("nan")
    return {
        "n_subjects": n_subjects,
        "median_level_db": float(np.nanmedian(subject_means)),
        "sd_reinsertion_db_median": sd_median,
        "sd_reinsertion_db_p95": sd_p95,
        "repeatability_coefficient_db": float(1.96 * math.sqrt(2.0) * sd_median),
        "icc_2_1": icc,
    }


def repeatability_summary(
    cube: TransferCube,
    bands: Sequence[Band],
    *,
    reference: float = 1.0,
) -> pd.DataFrame:
    """Band-level reinsertion repeatability per device.

    Parameters
    ----------
    cube:
        Measurement cube.  Complex transfer cubes are band-averaged with a
        power average (:meth:`TransferCube.band_levels`); level cubes are
        averaged arithmetically in dB (documented approximation).
    bands:
        Frequency bands to summarise.
    reference:
        Reference of the dB conversion.

    Returns
    -------
    pandas.DataFrame
        One row per (band, device) with columns ``band, band_center_hz,
        device_code, device, family, coupling, condition, n_subjects,
        median_level_db, sd_reinsertion_db_median, sd_reinsertion_db_p95,
        repeatability_coefficient_db, icc_2_1``.

        ``n_subjects`` counts the subjects with at least two valid reinsertions
        in that band/device cell (the subjects that contribute to the
        repeatability SD).  ``median_level_db`` is the median across subjects
        of the subject-level band level (mean over reinsertions).
        ``repeatability_coefficient_db`` = ``1.96 * sqrt(2) * median(SD)``.
    """
    band_list = tuple(bands)
    if not band_list:
        raise ValueError("bands must not be empty")
    for band in band_list:
        if not isinstance(band, Band):
            raise TypeError(f"bands must contain Band instances, got {type(band).__name__}")
    frame = _band_level_frame(cube, band_list, reference)
    rows: list[dict[str, Any]] = []
    for band in band_list:
        for device in cube.devices:
            matrix = _band_matrix(frame, band=band, device_code=device.code)
            if matrix is None:
                statistics = {
                    "n_subjects": 0,
                    "median_level_db": float("nan"),
                    "sd_reinsertion_db_median": float("nan"),
                    "sd_reinsertion_db_p95": float("nan"),
                    "repeatability_coefficient_db": float("nan"),
                    "icc_2_1": float("nan"),
                }
            else:
                statistics = _summarise_matrix(matrix)
            rows.append(
                {
                    "band": band.label,
                    "band_center_hz": float(band.center_hz),
                    "device_code": device.code,
                    "device": device.label,
                    "family": device.family,
                    "coupling": device.coupling.value,
                    "condition": device.condition.value if device.condition else None,
                    **statistics,
                }
            )
    result = pd.DataFrame(rows, columns=list(_SUMMARY_COLUMNS))
    logger.debug(
        "repeatability_summary: %d rows (%d bands × %d devices)",
        len(result),
        len(band_list),
        len(cube.devices),
    )
    return result


def _single_band(edge_hz: Sequence[float]) -> Band:
    edges = tuple(float(value) for value in edge_hz)
    if len(edges) != 2:
        raise ValueError(f"band_hz must contain exactly two edges, got {edges!r}")
    low, high = sorted(edges)
    if not (np.isfinite(low) and np.isfinite(high)) or low <= 0.0 or low >= high:
        raise ValueError(f"invalid band edges {edges!r}")
    return Band(
        label=f"{low:g}–{high:g} Hz",
        center_hz=float(math.sqrt(low * high)),
        low_hz=low,
        high_hz=high,
    )


def repeatability_by_device(
    cube: TransferCube,
    *,
    reference: float = 1.0,
    band_hz: Sequence[float] | None = None,
) -> pd.DataFrame:
    """Reinsertion repeatability per device over one wide band.

    Parameters
    ----------
    cube:
        Measurement cube.
    reference:
        Reference of the dB conversion.
    band_hz:
        Two band edges in Hz.  Defaults to the primary analysis band
        500–4000 Hz (hard-coded so this measurement function is
        configuration-independent).

    Returns
    -------
    pandas.DataFrame
        Same columns as :func:`repeatability_summary` with a single ``band``
        row set (one row per device).
    """
    edges = DEFAULT_BAND_HZ if band_hz is None else band_hz
    band = _single_band(edges)
    if band.high_hz <= float(np.min(cube.freq_hz)) or band.low_hz >= float(np.max(cube.freq_hz)):
        raise ValueError(
            f"band {band.label} does not overlap the cube frequency axis "
            f"[{float(np.min(cube.freq_hz)):.3g}, {float(np.max(cube.freq_hz)):.3g}] Hz"
        )
    return repeatability_summary(cube, (band,), reference=reference)
