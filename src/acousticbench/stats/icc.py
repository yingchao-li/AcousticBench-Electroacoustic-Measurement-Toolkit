"""Intraclass correlation coefficients (ICC) for measurement reliability.

ICC(2,1) is the absolute-agreement, two-way random-effects model with a single
measurement (Shrout & Fleiss, 1979, ICC(2,1) = "ICC(A,1)").  It is the
appropriate reliability coefficient for the three reinsertions of the same
earpiece: subjects are the random effect of interest, reinsertions are the
repeated measurements.

The two-way random-effects ANOVA (subjects × raters) yields

.. math::

    MS_R = SS_R/(n-1), \\quad MS_C = SS_C/(k-1), \\quad MS_E = SS_E/((n-1)(k-1))

with :math:`n` subjects and :math:`k` reinsertions, and

.. math::

    \\mathrm{ICC}(2,1) =
        \\frac{MS_R - MS_E}{MS_R + (k-1)MS_E + k(MS_C - MS_E)/n}.

Subjects with any missing repetition are dropped (complete-case analysis) and
the resulting number of subjects is always reported.  Missing values are never
imputed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import scipy.stats as st

from acousticbench.logging_utils import get_logger

__all__ = ["IccResult", "icc_2_1"]

logger = get_logger(__name__)

_DEFAULT_CI_RESAMPLES = 2000
_DEFAULT_SEED = 20260422


@dataclass(frozen=True)
class IccResult:
    """Result of an intraclass correlation analysis.

    Attributes
    ----------
    icc:
        ICC estimate.  NaN when the ANOVA is fully degenerate (all entries
        identical).
    f_value:
        F statistic of the subject effect (``MS_R / MS_E``).
    df1, df2:
        Degrees of freedom of the F test (``n - 1``, ``(n - 1)(k - 1)``).
    p_value:
        p-value of the F test.
    n_subjects:
        Number of subjects with a complete set of ratings.
    n_raters:
        Number of raters (reinsertions).
    model:
        ``"ICC(2,1)"``.
    ci_low, ci_high:
        Optional subject-level bootstrap percentile interval.
    """

    icc: float
    f_value: float
    df1: int
    df2: int
    p_value: float
    n_subjects: int
    n_raters: int
    model: str = "ICC(2,1)"
    ci_low: float | None = None
    ci_high: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the result as a plain dictionary."""
        return {
            "icc": self.icc,
            "f_value": self.f_value,
            "df1": self.df1,
            "df2": self.df2,
            "p_value": self.p_value,
            "n_subjects": self.n_subjects,
            "n_raters": self.n_raters,
            "model": self.model,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
        }


def _prepare(values: Any) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim != 2:
        raise ValueError(
            f"values must be a 2-D (n_subjects, n_raters) array, got shape {array.shape}"
        )
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"values must be numeric, got dtype {array.dtype}")
    array = np.asarray(array, dtype=float)
    if array.shape[0] < 2:
        raise ValueError(f"ICC requires at least 2 subjects, got {array.shape[0]}")
    if array.shape[1] < 2:
        raise ValueError(f"ICC requires at least 2 raters/reinsertions, got {array.shape[1]}")
    return array


def _anova_two_way(array: np.ndarray) -> tuple[float, float, float, int, int, int]:
    """Return ``(SS_R, SS_C, SS_E, df_R, df_C, df_E)`` of the two-way ANOVA."""
    n, k = array.shape
    grand = float(np.mean(array))
    row_means = np.mean(array, axis=1)
    column_means = np.mean(array, axis=0)
    ss_total = float(np.sum((array - grand) ** 2))
    ss_rows = float(k * np.sum((row_means - grand) ** 2))
    ss_columns = float(n * np.sum((column_means - grand) ** 2))
    ss_error = max(ss_total - ss_rows - ss_columns, 0.0)
    return ss_rows, ss_columns, ss_error, n - 1, k - 1, (n - 1) * (k - 1)


def _icc_from_anova(ss_rows: float, ss_columns: float, ss_error: float, n: int, k: int) -> dict[str, float]:
    ms_rows = ss_rows / (n - 1)
    ms_columns = ss_columns / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))
    denominator = ms_rows + (k - 1) * ms_error + k * (ms_columns - ms_error) / n
    if denominator <= 0.0:
        icc = float("nan")
    else:
        icc = (ms_rows - ms_error) / denominator
    if ms_error == 0.0:
        f_value = float("inf") if ms_rows > 0.0 else float("nan")
        p_value = 0.0 if ms_rows > 0.0 else float("nan")
    else:
        f_value = ms_rows / ms_error
        p_value = float(st.f.sf(f_value, n - 1, (n - 1) * (k - 1)))
    return {
        "icc": float(icc),
        "f_value": float(f_value),
        "ms_rows": float(ms_rows),
        "ms_columns": float(ms_columns),
        "ms_error": float(ms_error),
        "p_value": float(p_value),
    }


def _bootstrap_icc(
    array: np.ndarray,
    confidence: float,
    n_resamples: int,
    seed: int,
) -> tuple[float | None, float | None]:
    if int(n_resamples) < 20:
        raise ValueError(
            f"n_resamples must be >= 20 for a bootstrap ICC interval, got {n_resamples!r}"
        )
    n = array.shape[0]
    k = array.shape[1]
    rng = np.random.default_rng(int(seed))
    draws: list[float] = []
    for _ in range(int(n_resamples)):
        index = rng.integers(0, n, size=n)
        ss_rows, ss_columns, ss_error, df1, df2, df3 = _anova_two_way(array[index])
        if df1 <= 0 or df2 <= 0 or df3 <= 0:
            continue
        statistics = _icc_from_anova(ss_rows, ss_columns, ss_error, n, k)
        value = statistics["icc"]
        if np.isfinite(value):
            draws.append(value)
    if len(draws) < 20:
        logger.warning(
            "icc bootstrap: only %d/%d resamples produced a finite ICC; CI omitted",
            len(draws),
            int(n_resamples),
        )
        return None, None
    alpha = 1.0 - float(confidence)
    low, high = np.percentile(draws, [100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)])
    return float(low), float(high)


def icc_2_1(
    values: Any,
    *,
    confidence: float | None = None,
    n_resamples: int = _DEFAULT_CI_RESAMPLES,
    seed: int = _DEFAULT_SEED,
) -> IccResult:
    """ICC(2,1) — absolute agreement, two-way random effects, single rater.

    Parameters
    ----------
    values:
        Array of shape ``(n_subjects, n_raters)``, e.g. band levels per
        subject × reinsertion.  Subjects with any NaN entry are dropped.
    confidence:
        If not ``None``, add a subject-level percentile bootstrap confidence
        interval of the ICC.
    n_resamples:
        Number of bootstrap resamples (only used when ``confidence`` is set).
    seed:
        Seed of the bootstrap generator (deterministic intervals).

    Returns
    -------
    IccResult
        ICC estimate, two-way ANOVA F test of the subject effect and the
        number of complete subjects used.

    Notes
    -----
    ICC(2,1) is computed from the two-way random-effects ANOVA as

    ``(MS_R - MS_E) / (MS_R + (k-1) MS_E + k (MS_C - MS_E) / n)``.

    If the residual mean square is exactly zero (perfect within-subject
    agreement) the F statistic is infinite and the p-value is zero; if all
    values are identical the ICC is undefined and NaN is returned.
    """
    array = _prepare(values)
    complete = np.isfinite(array).all(axis=1)
    n_subjects = int(complete.sum())
    if n_subjects < 2:
        raise ValueError(
            f"ICC requires at least 2 subjects with a complete set of ratings, got {n_subjects}"
        )
    data = array[complete]
    n, k = data.shape
    ss_rows, ss_columns, ss_error, _, _, _ = _anova_two_way(data)
    statistics = _icc_from_anova(ss_rows, ss_columns, ss_error, n, k)

    ci_low: float | None = None
    ci_high: float | None = None
    if confidence is not None:
        if not 0.0 < float(confidence) < 1.0:
            raise ValueError(f"confidence must lie in (0, 1), got {confidence!r}")
        ci_low, ci_high = _bootstrap_icc(data, float(confidence), n_resamples, seed)

    result = IccResult(
        icc=statistics["icc"],
        f_value=statistics["f_value"],
        df1=n - 1,
        df2=(n - 1) * (k - 1),
        p_value=statistics["p_value"],
        n_subjects=n,
        n_raters=k,
        model="ICC(2,1)",
        ci_low=ci_low,
        ci_high=ci_high,
    )
    logger.debug(
        "ICC(2,1): icc=%.4f F=%.4g p=%.4g n=%d k=%d",
        result.icc,
        result.f_value,
        result.p_value,
        n,
        k,
    )
    return result
