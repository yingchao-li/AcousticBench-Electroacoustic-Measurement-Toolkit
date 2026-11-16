"""Descriptive statistics with explicit NaN semantics.

The measurements analysed by AcousticBench contain two kinds of "missing"
information (measured NaN and structurally invalid values).  Both are
represented as NaN in the analysis arrays, and **neither is ever imputed**.
Every function in this module therefore excludes NaN and reports how many
observations were actually used.

The subject is the independent statistical unit of the study: the three
reinsertions are technical repeats.  :func:`subject_means` is the canonical
helper that collapses the reinsertions within a subject *before* any
inferential statistics are computed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as st

from acousticbench.logging_utils import get_logger

__all__ = ["describe_array", "summarize_layout", "subject_means"]

logger = get_logger(__name__)

#: Percentiles reported by :func:`summarize_layout`.
SUMMARY_PERCENTILES: tuple[float, ...] = (0.05, 0.25, 0.75, 0.95)


def _finite(values: Any, *, name: str = "values") -> np.ndarray:
    """Return the finite entries of a 1-D numeric sample as ``float``."""
    array = np.asarray(values)
    if array.ndim == 0:
        raise ValueError(f"{name} must be a sequence, got a scalar")
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"{name} must be numeric, got dtype {array.dtype}")
    array = np.asarray(array, dtype=float).ravel()
    return array[np.isfinite(array)]


def describe_array(values: Any, *, confidence: float = 0.95) -> dict[str, Any]:
    """Describe a sample, excluding NaN and infinite entries.

    Parameters
    ----------
    values:
        One-dimensional (or flattenable) numeric sample.
    confidence:
        Confidence level of the normal/t interval of the mean.  Must lie in
        ``(0, 1)``.

    Returns
    -------
    dict
        ``n`` (number of finite observations), ``mean``, ``sd`` (sample
        standard deviation, ``ddof=1``), ``median``, ``iqr`` (interquartile
        range), ``min``, ``max``, ``se`` (standard error of the mean),
        ``ci_low`` and ``ci_high`` (t-based interval of the mean).  When no
        finite observation exists, ``n`` is 0 and every statistic is NaN;
        when only one observation exists, ``sd``/``se``/CI are NaN.

    Notes
    -----
    The confidence interval is the usual Student-t interval
    ``mean ± t_{1-α/2, n-1} · sd/√n``.  It describes the precision of the
    mean, it is *not* the bootstrap subject-level interval used for inference
    in the experiments (see :mod:`acousticbench.stats.bootstrap`).
    """
    if not 0.0 < float(confidence) < 1.0:
        raise ValueError(f"confidence must lie in (0, 1), got {confidence!r}")
    data = _finite(values)
    n = int(data.size)
    result: dict[str, Any] = {
        "n": n,
        "mean": float("nan"),
        "sd": float("nan"),
        "median": float("nan"),
        "iqr": float("nan"),
        "min": float("nan"),
        "max": float("nan"),
        "se": float("nan"),
        "standard_error": float("nan"),
        "ci_low": float("nan"),
        "ci_high": float("nan"),
    }
    if n == 0:
        logger.debug("describe_array: no finite observation")
        return result

    result["mean"] = float(np.mean(data))
    result["median"] = float(np.median(data))
    q25, q75 = np.percentile(data, [25.0, 75.0])
    result["iqr"] = float(q75 - q25)
    result["min"] = float(np.min(data))
    result["max"] = float(np.max(data))
    if n >= 2:
        sd = float(np.std(data, ddof=1))
        se = sd / np.sqrt(n)
        result["sd"] = sd
        result["se"] = float(se)
        result["standard_error"] = float(se)
        if se > 0.0:
            alpha = 1.0 - float(confidence)
            quantile = float(st.t.ppf(1.0 - alpha / 2.0, n - 1))
            result["ci_low"] = float(result["mean"] - quantile * se)
            result["ci_high"] = float(result["mean"] + quantile * se)
        else:
            result["ci_low"] = result["ci_high"] = float(result["mean"])
    return result


def summarize_layout(
    df: pd.DataFrame,
    *,
    value_col: str,
    group_cols: Sequence[str],
) -> pd.DataFrame:
    """Summarise a tidy DataFrame by grouping columns, excluding NaN.

    Parameters
    ----------
    df:
        Tidy input frame (one row per observation).
    value_col:
        Numeric column to summarise.
    group_cols:
        Columns that define the groups.  An empty sequence summarises the
        whole frame as a single group (the index is then empty).

    Returns
    -------
    pandas.DataFrame
        One row per group with ``group_cols`` followed by ``n`` (finite
        observations), ``mean``, ``sd`` (``ddof=1``; NaN for ``n < 2``),
        ``median``, ``iqr``, ``p05``, ``p25``, ``p75``, ``p95``, ``min`` and
        ``max``.
    """
    if value_col not in df.columns:
        raise ValueError(f"value_col {value_col!r} not in DataFrame columns")
    groups = list(group_cols)
    missing = [c for c in groups if c not in df.columns]
    if missing:
        raise ValueError(f"group_cols not in DataFrame columns: {missing}")
    if value_col in groups:
        raise ValueError("value_col must not also be a grouping column")

    frame = df.loc[:, [*groups, value_col]].copy()
    frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
    if groups:
        by = groups
    else:
        frame["_all"] = 0
        by = ["_all"]

    grouped = frame.groupby(by, dropna=False, sort=True)[value_col]
    out = grouped.agg(
        n="count",
        mean="mean",
        sd=lambda s: (
            float(np.std(s.dropna().to_numpy(dtype=float), ddof=1))
            if s.count() >= 2
            else np.nan
        ),
        median="median",
        min="min",
        max="max",
    )
    quantiles = grouped.quantile(SUMMARY_PERCENTILES).unstack()
    quantiles.columns = [f"p{int(round(q * 100)):02d}" for q in SUMMARY_PERCENTILES]
    out = out.join(quantiles)
    out["iqr"] = out["p75"] - out["p25"]
    columns = [
        "n",
        "mean",
        "sd",
        "median",
        "iqr",
        "p05",
        "p25",
        "p75",
        "p95",
        "min",
        "max",
    ]
    out = out.loc[:, columns]
    if not groups:
        out.index = pd.Index([], name=None)
        out = out.reset_index(drop=True)
    return out.reset_index() if groups else out


def subject_means(
    df: pd.DataFrame,
    *,
    value_col: str,
    subject_col: str = "subject",
    group_cols: Sequence[str] = ("device_code",),
) -> pd.DataFrame:
    """Collapse technical repeats to one value per subject.

    The three reinsertions are technical repeats, not independent
    observations.  This helper averages all finite values of ``value_col``
    within each ``(group_cols, subject_col)`` cell and returns the collapsed
    frame.  Subjects without any finite value are dropped (they carry no
    information and must not enter a paired test).

    Parameters
    ----------
    df:
        Tidy long-format frame with one row per (subject, repeat).
    value_col:
        Numeric value column.
    subject_col:
        Column identifying the independent statistical unit.
    group_cols:
        Remaining observational columns (e.g. ``device_code``, ``band``) that
        must be preserved.  Reinsertion columns (``reinsertion``) are the
        repeats and are removed from the result.

    Returns
    -------
    pandas.DataFrame
        One row per ``(group_cols, subject_col)`` with ``value_col`` replaced
        by the within-subject mean and an additional ``n_reinsertions``
        column counting the finite repeats that entered the mean.
    """
    if value_col not in df.columns:
        raise ValueError(f"value_col {value_col!r} not in DataFrame columns")
    if subject_col not in df.columns:
        raise ValueError(f"subject_col {subject_col!r} not in DataFrame columns")
    groups = [c for c in group_cols if c != subject_col]
    missing = [c for c in groups if c not in df.columns]
    if missing:
        raise ValueError(f"group_cols not in DataFrame columns: {missing}")
    if value_col in groups or value_col == subject_col:
        raise ValueError("value_col must be distinct from the grouping columns")

    frame = df.loc[:, [*groups, subject_col, value_col]].copy()
    frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
    keys = [*groups, subject_col]
    grouped = frame.groupby(keys, dropna=False, sort=True)[value_col]
    collapsed = grouped.agg(**{value_col: "mean", "n_reinsertions": "count"}).reset_index()
    collapsed = collapsed.loc[collapsed["n_reinsertions"] > 0].reset_index(drop=True)
    logger.debug(
        "subject_means: %d rows -> %d subject-level rows", len(df), len(collapsed)
    )
    return collapsed
