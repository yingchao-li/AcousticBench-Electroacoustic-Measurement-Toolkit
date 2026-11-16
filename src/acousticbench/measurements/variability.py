"""Between-subject variability and one-way random-effects variance components.

The subject is the independent unit.  This module quantifies how much of the
observed spread of band levels is real between-subject variability and how
much is reinsertion (measurement) noise.

One-way random-effects model
----------------------------
For a balanced matrix :math:`x_{ij}` with :math:`i = 1..n` subjects and
:math:`j = 1..k` reinsertions,

.. math::

    x_{ij} = \\mu + b_i + e_{ij}, \\qquad
    b_i \\sim N(0, \\sigma^2_b), \\quad e_{ij} \\sim N(0, \\sigma^2_w)

with the ANOVA mean squares

.. math::

    MS_B = \\frac{k \\sum_i (\\bar x_{i\\cdot} - \\bar x)^2}{n-1}, \\qquad
    MS_W = \\frac{\\sum_{ij} (x_{ij} - \\bar x_{i\\cdot})^2}{n(k-1)}.

The variance-component estimators are

.. math::

    \\hat\\sigma^2_w = MS_W, \\qquad
    \\hat\\sigma^2_b = \\frac{MS_B - MS_W}{k}

(the estimator of :math:`\\sigma^2_b` can be negative; the raw value is
reported, not truncated) and the single-measurement ICC is

.. math::

    \\mathrm{ICC}(1,1) = \\frac{MS_B - MS_W}{MS_B + (k-1) MS_W}.

Subjects with any missing reinsertion are excluded from the ANOVA (complete
case) and the number used is reported; nothing is imputed.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from acousticbench.data.dataset import TransferCube
from acousticbench.logging_utils import get_logger
from acousticbench.measurements.repeatability import (
    DEFAULT_BAND_HZ,
    _band_level_frame,
    _single_band,
)
from acousticbench.stats.bands import Band

__all__ = [
    "inter_subject_variability",
    "variability_by_device",
    "variance_components",
]

logger = get_logger(__name__)

_VARIABILITY_COLUMNS = (
    "band",
    "band_center_hz",
    "device_code",
    "device",
    "family",
    "coupling",
    "condition",
    "n_subjects",
    "n_subjects_complete",
    "mean_level_db",
    "sd_between_subject_db",
    "iqr_db",
    "range_db",
    "cv_db",
    "between_subject_variance_db2",
    "within_subject_variance_db2",
    "icc_1_1",
)


def _prepare_matrix(values: Any) -> tuple[np.ndarray, int]:
    """Validate a subjects × repeats matrix and drop incomplete subjects."""
    array = np.asarray(values)
    if array.ndim != 2:
        raise ValueError(
            f"values must be a 2-D (n_subjects, n_repeats) array, got shape {array.shape}"
        )
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"values must be numeric, got dtype {array.dtype}")
    array = np.asarray(array, dtype=float)
    if array.shape[0] < 2:
        raise ValueError(f"variance_components requires at least 2 subjects, got {array.shape[0]}")
    if array.shape[1] < 2:
        raise ValueError(f"variance_components requires at least 2 repeats, got {array.shape[1]}")
    complete = np.isfinite(array).all(axis=1)
    data = array[complete]
    if data.shape[0] < 2:
        raise ValueError(
            "variance_components requires at least 2 subjects with a complete set of repeats, "
            f"got {data.shape[0]}"
        )
    return data, int(array.shape[0] - data.shape[0])


def variance_components(values: Any) -> dict[str, Any]:
    """One-way random-effects variance components of a subjects × repeats matrix.

    Parameters
    ----------
    values:
        Array of shape ``(n_subjects, n_repeats)``, possibly containing NaN.
        Rows (subjects) with any missing repeat are excluded.

    Returns
    -------
    dict
        ``n_subjects`` (complete rows used), ``n_subjects_dropped``,
        ``n_repeats``, ``grand_mean``, ``ss_between``, ``ss_within``,
        ``df_between``, ``df_within``, ``ms_between``, ``ms_within``,
        ``between_subject_variance`` :math:`\\hat\\sigma^2_b`,
        ``within_subject_variance`` :math:`\\hat\\sigma^2_w` and
        ``icc_1_1``.  ``icc_1_1`` is NaN if the ANOVA denominator is zero.
    """
    data, dropped = _prepare_matrix(values)
    n, k = data.shape
    grand_mean = float(np.mean(data))
    subject_means = np.mean(data, axis=1)
    ss_between = float(k * np.sum((subject_means - grand_mean) ** 2))
    ss_within = float(np.sum((data - subject_means[:, None]) ** 2))
    df_between = n - 1
    df_within = n * (k - 1)
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    between_variance = (ms_between - ms_within) / k
    denominator = ms_between + (k - 1) * ms_within
    icc = (ms_between - ms_within) / denominator if denominator > 0.0 else float("nan")
    result: dict[str, Any] = {
        "n_subjects": n,
        "n_subjects_dropped": dropped,
        "n_repeats": k,
        "grand_mean": grand_mean,
        "ss_between": ss_between,
        "ss_within": ss_within,
        "df_between": df_between,
        "df_within": df_within,
        "ms_between": ms_between,
        "ms_within": ms_within,
        "between_subject_variance": float(between_variance),
        "within_subject_variance": float(ms_within),
        "icc_1_1": float(icc),
    }
    logger.debug(
        "variance_components: n=%d k=%d sigma2_b=%.4f sigma2_w=%.4f ICC(1,1)=%.4f",
        n,
        k,
        between_variance,
        ms_within,
        icc,
    )
    return result


def _empty_variability_row() -> dict[str, Any]:
    """Return the no-data row of :func:`_variability_row`."""
    return {
        "n_subjects": 0,
        "n_subjects_complete": 0,
        "mean_level_db": float("nan"),
        "sd_between_subject_db": float("nan"),
        "iqr_db": float("nan"),
        "range_db": float("nan"),
        "cv_db": float("nan"),
        "between_subject_variance_db2": float("nan"),
        "within_subject_variance_db2": float("nan"),
        "icc_1_1": float("nan"),
    }


def _variability_row(
    matrix: np.ndarray,
) -> dict[str, Any]:
    """Between-subject statistics for one subjects × reinsertions matrix."""
    if matrix.size == 0:
        return _empty_variability_row()
    counts = np.isfinite(matrix).sum(axis=1)
    present = counts > 0
    n_subjects = int(present.sum())
    with warnings.catch_warnings(), np.errstate(invalid="ignore"):
        warnings.simplefilter("ignore", category=RuntimeWarning)
        subject_means = np.nanmean(matrix, axis=1)
        subject_means = subject_means[present]
    if n_subjects == 0:
        return _empty_variability_row()
    mean_level = float(np.mean(subject_means))
    sd_between = float(np.std(subject_means, ddof=1)) if n_subjects >= 2 else float("nan")
    if n_subjects >= 2:
        q25, q75 = np.percentile(subject_means, [25.0, 75.0])
        iqr = float(q75 - q25)
        spread = float(np.max(subject_means) - np.min(subject_means))
    else:
        iqr = float("nan")
        spread = float("nan")
    cv = 100.0 * sd_between / mean_level if abs(mean_level) > 1e-12 else float("nan")
    try:
        components = variance_components(matrix)
    except ValueError as exc:
        logger.debug("variance components not computable: %s", exc)
        components = {
            "n_subjects": 0,
            "between_subject_variance": float("nan"),
            "within_subject_variance": float("nan"),
            "icc_1_1": float("nan"),
        }
    return {
        "n_subjects": n_subjects,
        "n_subjects_complete": int(components["n_subjects"]),
        "mean_level_db": mean_level,
        "sd_between_subject_db": sd_between,
        "iqr_db": iqr,
        "range_db": spread,
        "cv_db": float(cv),
        "between_subject_variance_db2": float(components["between_subject_variance"]),
        "within_subject_variance_db2": float(components["within_subject_variance"]),
        "icc_1_1": float(components["icc_1_1"]),
    }


def inter_subject_variability(
    cube: TransferCube,
    bands: Sequence[Band],
    *,
    reference: float = 1.0,
) -> pd.DataFrame:
    """Between-subject variability of band levels per device.

    Parameters
    ----------
    cube:
        Measurement cube.  Complex transfer cubes are band-averaged with a
        power average; level cubes are averaged arithmetically in dB.
    bands:
        Frequency bands to summarise.
    reference:
        Reference of the dB conversion.

    Returns
    -------
    pandas.DataFrame
        One row per (band, device) with columns ``band, band_center_hz,
        device_code, device, family, coupling, condition, n_subjects,
        n_subjects_complete, mean_level_db, sd_between_subject_db, iqr_db,
        range_db, cv_db, between_subject_variance_db2,
        within_subject_variance_db2, icc_1_1``.

        ``n_subjects`` counts subjects with at least one valid band level;
        ``n_subjects_complete`` counts subjects with a complete set of
        reinsertion levels (the ANOVA sample size).  ``sd_between_subject_db``
        is the sample SD (``ddof=1``) of the subject-level band levels (mean
        over reinsertions), ``cv_db`` is ``100 * sd / mean`` (NaN when the
        mean is zero) and the variance components are the one-way
        random-effects estimates (:func:`variance_components`).
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
            subset = frame.loc[
                (frame["band"] == band.label) & (frame["device_code"] == device.code),
                ["subject", "reinsertion", "level_db"],
            ]
            if subset.empty:
                statistics = _empty_variability_row()
            else:
                matrix = subset.pivot(
                    index="subject", columns="reinsertion", values="level_db"
                ).to_numpy(dtype=float)
                statistics = _variability_row(matrix)
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
    return pd.DataFrame(rows, columns=list(_VARIABILITY_COLUMNS))


def variability_by_device(
    cube: TransferCube,
    *,
    reference: float = 1.0,
    band_hz: Sequence[float] = DEFAULT_BAND_HZ,
) -> pd.DataFrame:
    """Between-subject variability per device over one wide band.

    Parameters
    ----------
    cube:
        Measurement cube.
    reference:
        Reference of the dB conversion.
    band_hz:
        Two band edges in Hz (default 500–4000 Hz).

    Returns
    -------
    pandas.DataFrame
        Same columns as :func:`inter_subject_variability`, one row per device.
    """
    band = _single_band(band_hz)
    if band.high_hz <= float(np.min(cube.freq_hz)) or band.low_hz >= float(np.max(cube.freq_hz)):
        raise ValueError(
            f"band {band.label} does not overlap the cube frequency axis "
            f"[{float(np.min(cube.freq_hz)):.3g}, {float(np.max(cube.freq_hz)):.3g}] Hz"
        )
    return inter_subject_variability(cube, (band,), reference=reference)
