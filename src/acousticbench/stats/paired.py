"""Paired inference for subject-level data.

The three reinsertions are technical repeats.  Every function in this module
expects **one value per subject** (already collapsed across reinsertions, see
:func:`acousticbench.stats.descriptive.subject_means`); the subject index is
the pairing unit.  Complete finite pairs are used and the number of complete
pairs is always reported.  No missing value is imputed and no significance is
manufactured for degenerate (zero-variance) differences.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import scipy.stats as st

from acousticbench.logging_utils import get_logger
from acousticbench.stats.effect_size import cohen_dz, rank_biserial

__all__ = [
    "PairedTestResult",
    "normality_check",
    "paired_summary",
    "paired_t_test",
    "wilcoxon_signed_rank",
]

logger = get_logger(__name__)

_ALTERNATIVES = ("two-sided", "less", "greater")
_ZERO_METHODS = ("pratt", "wilcox", "zsplit")


@dataclass(frozen=True)
class PairedTestResult:
    """Result of a paired (subject-level) t-test.

    Attributes
    ----------
    method:
        Always ``"paired_t_test"``.
    n:
        Number of complete finite pairs used.
    mean_a, mean_b:
        Means of the two paired samples over the complete pairs.
    mean_diff:
        Mean of the paired differences ``a - b``.
    sd_diff:
        Sample standard deviation of the differences (``ddof=1``).
    t:
        Test statistic.
    df:
        Degrees of freedom (``n - 1``).
    p_value:
        p-value of the requested alternative.
    ci_low, ci_high:
        Confidence interval of the mean difference.  One-sided alternatives
        report an infinite bound on the opposite side.
    effect_size:
        Cohen's :math:`d_z`.
    effect_size_name:
        ``"cohen_dz"``.
    alternative:
        The alternative hypothesis used.
    """

    method: str
    n: int
    mean_a: float
    mean_b: float
    mean_diff: float
    sd_diff: float
    t: float
    df: int
    p_value: float
    ci_low: float
    ci_high: float
    effect_size: float
    effect_size_name: str
    alternative: str = "two-sided"

    def to_dict(self) -> dict[str, Any]:
        """Return the result as a plain dictionary."""
        return {
            "method": self.method,
            "n": self.n,
            "mean_a": self.mean_a,
            "mean_b": self.mean_b,
            "mean_diff": self.mean_diff,
            "sd_diff": self.sd_diff,
            "t": self.t,
            "df": self.df,
            "p_value": self.p_value,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "effect_size": self.effect_size,
            "effect_size_name": self.effect_size_name,
            "alternative": self.alternative,
        }


def _paired_arrays(a: Any, b: Any) -> tuple[np.ndarray, np.ndarray]:
    """Validate and align two paired samples, keeping complete finite pairs."""
    first = np.asarray(a)
    second = np.asarray(b)
    if first.ndim != 1 or second.ndim != 1:
        raise ValueError(
            f"paired samples must be 1-D, got shapes {first.shape} and {second.shape}"
        )
    if first.size != second.size:
        raise ValueError(
            f"paired samples must have equal length, got {first.size} and {second.size}"
        )
    if not (np.issubdtype(first.dtype, np.number) and np.issubdtype(second.dtype, np.number)):
        raise ValueError("paired samples must be numeric")
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    complete = np.isfinite(first) & np.isfinite(second)
    return first[complete], second[complete]


def _validate_alternative(alternative: str) -> str:
    normalised = str(alternative).strip().lower()
    if normalised not in _ALTERNATIVES:
        raise ValueError(
            f"alternative must be one of {_ALTERNATIVES}, got {alternative!r}"
        )
    return normalised


def paired_t_test(
    a: Any,
    b: Any,
    *,
    confidence: float = 0.95,
    alternative: str = "two-sided",
) -> PairedTestResult:
    """Paired Student t-test with a parametric CI of the mean difference.

    Parameters
    ----------
    a, b:
        One value per subject, paired.  Non-finite pairs are excluded
        (listwise).
    confidence:
        Confidence level of the interval of ``mean(a - b)``.
    alternative:
        ``"two-sided"`` (default), ``"less"`` (a < b) or ``"greater"``.

    Returns
    -------
    PairedTestResult
        Uses :func:`scipy.stats.ttest_rel` for the test statistic and p-value
        and the Student-t quantile for the interval.

    Raises
    ------
    ValueError
        If the samples are not 1-D / not equal length, if fewer than 3
        complete finite pairs remain, if the confidence level is invalid or if
        the paired differences have zero variance (the t statistic and
        Cohen's :math:`d_z` are then undefined).
    """
    if not 0.0 < float(confidence) < 1.0:
        raise ValueError(f"confidence must lie in (0, 1), got {confidence!r}")
    alt = _validate_alternative(alternative)
    first, second = _paired_arrays(a, b)
    n = int(first.size)
    if n < 3:
        raise ValueError(f"paired_t_test requires at least 3 complete pairs, got {n}")

    differences = first - second
    mean_diff = float(np.mean(differences))
    sd_diff = float(np.std(differences, ddof=1))
    if not np.isfinite(sd_diff) or sd_diff == 0.0:
        raise ValueError(
            "paired_t_test is undefined: the paired differences have zero variance"
        )
    df = n - 1
    standard_error = sd_diff / np.sqrt(n)
    test = st.ttest_rel(first, second, alternative=alt)
    statistic = float(test.statistic)
    p_value = float(test.pvalue)

    alpha = 1.0 - float(confidence)
    if alt == "two-sided":
        quantile = float(st.t.ppf(1.0 - alpha / 2.0, df))
        ci_low = mean_diff - quantile * standard_error
        ci_high = mean_diff + quantile * standard_error
    elif alt == "less":
        quantile = float(st.t.ppf(1.0 - alpha, df))
        ci_low = float("-inf")
        ci_high = mean_diff + quantile * standard_error
    else:  # "greater"
        quantile = float(st.t.ppf(1.0 - alpha, df))
        ci_low = mean_diff - quantile * standard_error
        ci_high = float("inf")

    result = PairedTestResult(
        method="paired_t_test",
        n=n,
        mean_a=float(np.mean(first)),
        mean_b=float(np.mean(second)),
        mean_diff=mean_diff,
        sd_diff=sd_diff,
        t=statistic,
        df=df,
        p_value=p_value,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        effect_size=cohen_dz(differences),
        effect_size_name="cohen_dz",
        alternative=alt,
    )
    logger.debug(
        "paired_t_test: n=%d mean_diff=%.4f t=%.4f p=%.4g", n, mean_diff, statistic, p_value
    )
    return result


def wilcoxon_signed_rank(
    a: Any,
    b: Any,
    *,
    alternative: str = "two-sided",
    zero_method: str = "wilcox",
    correction: bool = False,
) -> dict[str, Any]:
    """Wilcoxon signed-rank test for paired subject-level samples.

    Parameters
    ----------
    a, b:
        One value per subject, paired.  Non-finite pairs are excluded.
    alternative:
        ``"two-sided"`` (default), ``"less"`` or ``"greater"``.
    zero_method:
        Zero-difference handling passed to :func:`scipy.stats.wilcoxon`:
        ``"wilcox"`` (default, discard zeros), ``"pratt"`` or ``"zsplit"``.
    correction:
        Apply the continuity correction (passed to SciPy).

    Returns
    -------
    dict
        ``method``, ``n`` (complete pairs), ``statistic``, ``p_value``,
        ``alternative``, ``zero_method``, ``correction``, ``median_diff``,
        ``effect_size`` (rank-biserial) and ``effect_size_name``.

    Raises
    ------
    ValueError
        On invalid input, fewer than 3 complete pairs, or when SciPy cannot
        compute the statistic (e.g. all differences are zero).
    """
    alt = _validate_alternative(alternative)
    normalised_zero = str(zero_method).strip().lower()
    if normalised_zero not in _ZERO_METHODS:
        raise ValueError(
            f"zero_method must be one of {_ZERO_METHODS}, got {zero_method!r}"
        )
    first, second = _paired_arrays(a, b)
    n = int(first.size)
    if n < 3:
        raise ValueError(
            f"wilcoxon_signed_rank requires at least 3 complete pairs, got {n}"
        )
    differences = first - second
    try:
        test = st.wilcoxon(
            first,
            second,
            alternative=alt,
            zero_method=normalised_zero,
            correction=bool(correction),
        )
    except ValueError as exc:
        raise ValueError(f"Wilcoxon signed-rank test failed: {exc}") from exc
    return {
        "method": "wilcoxon_signed_rank",
        "n": n,
        "statistic": float(test.statistic),
        "p_value": float(test.pvalue),
        "alternative": alt,
        "zero_method": normalised_zero,
        "correction": bool(correction),
        "median_diff": float(np.median(differences)),
        "mean_diff": float(np.mean(differences)),
        "effect_size": rank_biserial(differences),
        "effect_size_name": "rank_biserial",
    }


def normality_check(values: Any) -> dict[str, Any]:
    """Shapiro-Wilk normality check, excluding non-finite entries.

    Parameters
    ----------
    values:
        Sample to test (e.g. the paired differences).

    Returns
    -------
    dict
        ``method`` (``"shapiro_wilk"``), ``n``, ``statistic``, ``p_value``,
        ``normal_at_0_05`` (``bool`` or ``None`` when the test cannot be
        computed) and ``note``.  For ``n < 3`` the statistic and p-value are
        NaN and ``normal_at_0_05`` is ``None``.
    """
    array = np.asarray(values, dtype=float).ravel()
    data = array[np.isfinite(array)]
    n = int(data.size)
    result: dict[str, Any] = {
        "method": "shapiro_wilk",
        "n": n,
        "statistic": float("nan"),
        "p_value": float("nan"),
        "normal_at_0_05": None,
        "note": "",
    }
    if n < 3:
        result["note"] = "Shapiro-Wilk requires at least 3 observations"
        return result
    test = st.shapiro(data)
    result["statistic"] = float(test.statistic)
    result["p_value"] = float(test.pvalue)
    result["normal_at_0_05"] = bool(float(test.pvalue) >= 0.05)
    result["note"] = (
        "no evidence against normality at alpha=0.05"
        if result["normal_at_0_05"]
        else "evidence against normality at alpha=0.05"
    )
    return result


def paired_summary(
    a: Any,
    b: Any,
    *,
    bootstrap: Any = None,
) -> dict[str, Any]:
    """Convenience summary: parametric test, Wilcoxon, effect sizes and bootstrap.

    Parameters
    ----------
    a, b:
        Paired subject-level samples.
    bootstrap:
        ``None`` (no bootstrap), a mapping of keyword arguments for
        :func:`acousticbench.stats.bootstrap.bootstrap_paired_ci`, or an object
        providing ``n_resamples``, ``confidence``, ``seed`` and ``method``
        attributes (e.g. :class:`acousticbench.config.BootstrapConfig`).

    Returns
    -------
    dict
        Flattened :meth:`PairedTestResult.to_dict` under the top level, plus
        ``"normality"``, ``"wilcoxon"`` and (when requested) ``"bootstrap"``
        with the nested bootstrap result and flat ``bootstrap_ci_low`` /
        ``bootstrap_ci_high`` / ``bootstrap_estimate`` / ``bootstrap_n`` keys.
    """
    from acousticbench.stats.bootstrap import bootstrap_paired_ci

    result = paired_t_test(a, b)
    summary: dict[str, Any] = result.to_dict()
    first, second = _paired_arrays(a, b)
    summary["normality"] = normality_check(first - second)
    summary["wilcoxon"] = wilcoxon_signed_rank(first, second)
    if bootstrap is not None:
        if isinstance(bootstrap, dict):
            kwargs = dict(bootstrap)
        else:
            kwargs = {
                "n_resamples": getattr(bootstrap, "n_resamples", 10000),
                "confidence": getattr(bootstrap, "confidence", 0.95),
                "seed": getattr(bootstrap, "seed", 20260422),
                "method": getattr(bootstrap, "method", "percentile"),
            }
        boot = bootstrap_paired_ci(first, second, **kwargs)
        summary["bootstrap"] = boot.to_dict()
        summary["bootstrap_estimate"] = boot.estimate
        summary["bootstrap_ci_low"] = boot.ci_low
        summary["bootstrap_ci_high"] = boot.ci_high
        summary["bootstrap_n"] = boot.n
    return summary
