"""Subject-level bootstrap confidence intervals.

The subject is the independent statistical unit.  Paired bootstrap intervals
therefore resample **subjects** (complete pairs), never individual
reinsertions.  All functions are deterministic given ``seed`` (a
:class:`numpy.random.Generator` created with :func:`numpy.random.default_rng`).

NaN policy
----------
Naive resampling of NaN entries would corrupt the statistic.  The default,
documented behaviour is therefore: **drop non-finite entries and record how
many finite observations were used in** :attr:`BootstrapResult.n`.  This is
reported, never silently hidden.  For paired data an entry is dropped as soon
as either member of the pair is non-finite (listwise deletion of the pair).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd
import scipy.stats as st

from acousticbench.logging_utils import get_logger

__all__ = [
    "BootstrapResult",
    "bootstrap_ci",
    "bootstrap_paired_ci",
    "cluster_bootstrap_ci",
]

logger = get_logger(__name__)

#: Default master seed (matches ``config/default.yaml``).
DEFAULT_SEED: int = 20260422
#: Default number of bootstrap resamples.
DEFAULT_N_RESAMPLES: int = 10000
#: Default confidence level.
DEFAULT_CONFIDENCE: float = 0.95


@dataclass(frozen=True)
class BootstrapResult:
    """Result of a subject-level bootstrap confidence interval.

    Attributes
    ----------
    estimate:
        The statistic evaluated on the observed sample (not on a resample).
    ci_low, ci_high:
        Lower and upper confidence limits.
    confidence:
        Confidence level, e.g. 0.95.
    n_resamples:
        Number of bootstrap resamples.
    method:
        ``"percentile"`` or ``"bca"``.
    seed:
        Seed of the random generator (reproducibility record).
    n:
        Number of finite observations (or resampled units) that entered the
        bootstrap.
    """

    estimate: float
    ci_low: float
    ci_high: float
    confidence: float
    n_resamples: int
    method: str
    seed: int
    n: int

    def to_dict(self) -> dict[str, Any]:
        """Return the result as a plain dictionary."""
        return {
            "estimate": self.estimate,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "confidence": self.confidence,
            "n_resamples": self.n_resamples,
            "method": self.method,
            "seed": self.seed,
            "n": self.n,
        }

    def __str__(self) -> str:
        return (
            f"{self.estimate:.6g} "
            f"[{self.ci_low:.6g}, {self.ci_high:.6g}] "
            f"({self.confidence:.0%} {self.method} bootstrap, "
            f"B={self.n_resamples}, n={self.n}, seed={self.seed})"
        )


def _as_numeric(values: Any, *, name: str) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim == 0:
        raise ValueError(f"{name} must be a sequence, got a scalar")
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"{name} must be numeric, got dtype {array.dtype}")
    return np.asarray(array, dtype=float).ravel()


def _validate_settings(
    statistic: Callable[[np.ndarray], float],
    n_resamples: int,
    confidence: float,
    method: str,
    seed: int,
) -> tuple[str, int]:
    if not callable(statistic):
        raise ValueError("statistic must be callable")
    if int(n_resamples) < 1:
        raise ValueError(f"n_resamples must be >= 1, got {n_resamples!r}")
    if not 0.0 < float(confidence) < 1.0:
        raise ValueError(f"confidence must lie in (0, 1), got {confidence!r}")
    normalised = str(method).strip().lower()
    if normalised not in {"percentile", "bca"}:
        raise ValueError(
            f"unknown bootstrap method {method!r}; expected 'percentile' or 'bca'"
        )
    return normalised, int(n_resamples)


def _check_statistic(statistic: Callable[[np.ndarray], float], sample: np.ndarray) -> float:
    value = statistic(sample)
    try:
        scalar = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("statistic must return a scalar") from exc
    if not np.isfinite(scalar):
        raise ValueError("statistic returned a non-finite value")
    return scalar


def _percentile_interval(
    distribution: np.ndarray, confidence: float
) -> tuple[float, float]:
    alpha = 1.0 - float(confidence)
    low, high = np.percentile(distribution, [100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)])
    return float(low), float(high)


def _bca_interval(
    sample: np.ndarray,
    distribution: np.ndarray,
    estimate: float,
    statistic: Callable[[np.ndarray], float],
    confidence: float,
) -> tuple[float, float]:
    """Bias-corrected and accelerated (BCa) bootstrap interval."""
    n = int(sample.size)
    if n < 3:
        raise ValueError("the BCa method requires at least 3 finite observations")
    proportion_less = float(np.mean(distribution < estimate))
    if proportion_less <= 0.0 or proportion_less >= 1.0:
        raise ValueError(
            "the BCa method failed: all bootstrap replicates lie on one side of the "
            "observed estimate (degenerate bootstrap distribution)"
        )
    z0 = float(st.norm.ppf(proportion_less))

    jackknife = np.empty(n, dtype=float)
    for index in range(n):
        subset = np.delete(sample, index)
        jackknife[index] = _check_statistic(statistic, subset)
    jack_mean = float(np.mean(jackknife))
    deviations = jack_mean - jackknife
    denominator = 6.0 * float(np.sum(deviations**2)) ** 1.5
    if denominator == 0.0:
        raise ValueError("the BCa method failed: zero jackknife variance")
    acceleration = float(np.sum(deviations**3)) / denominator

    alpha = 1.0 - float(confidence)
    z_levels = np.array([st.norm.ppf(alpha / 2.0), st.norm.ppf(1.0 - alpha / 2.0)])
    with np.errstate(divide="ignore", invalid="ignore"):
        adjusted = st.norm.cdf(
            z0 + (z0 + z_levels) / (1.0 - acceleration * (z0 + z_levels))
        )
    if not np.all(np.isfinite(adjusted)):
        raise ValueError("the BCa method failed: non-finite adjusted quantiles")
    low, high = np.percentile(distribution, 100.0 * adjusted)
    return float(low), float(high)


def bootstrap_ci(
    values: Any,
    *,
    statistic: Callable[[np.ndarray], float] = np.mean,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = DEFAULT_SEED,
    method: str = "percentile",
) -> BootstrapResult:
    """Subject-level percentile bootstrap CI of a one-sample statistic.

    Parameters
    ----------
    values:
        One-dimensional sample with one entry per independent subject.
    statistic:
        Callable mapping a 1-D array to a scalar (default :func:`numpy.mean`).
    n_resamples:
        Number of bootstrap resamples (default 10 000).
    confidence:
        Confidence level in ``(0, 1)``.
    seed:
        Seed for :func:`numpy.random.default_rng`; identical seeds give
        identical results.
    method:
        ``"percentile"`` (default) or ``"bca"``.

    Returns
    -------
    BootstrapResult
        The observed statistic, the confidence limits and the number of finite
        observations used (``n``).  Non-finite entries are dropped.

    Raises
    ------
    ValueError
        On invalid settings, fewer than two finite observations, or a statistic
        that returns a non-finite value / fails under resampling.
    """
    normalised, resamples = _validate_settings(statistic, n_resamples, confidence, method, seed)
    raw = _as_numeric(values, name="values")
    sample = raw[np.isfinite(raw)]
    n = int(sample.size)
    if n < 2:
        raise ValueError(f"bootstrap_ci requires at least 2 finite observations, got {n}")
    estimate = _check_statistic(statistic, sample)

    rng = np.random.default_rng(int(seed))
    indices = rng.integers(0, n, size=(resamples, n))
    distribution = np.empty(resamples, dtype=float)
    for index, draw in enumerate(indices):
        distribution[index] = _check_statistic(statistic, sample[draw])

    if normalised == "bca":
        ci_low, ci_high = _bca_interval(sample, distribution, estimate, statistic, confidence)
    else:
        ci_low, ci_high = _percentile_interval(distribution, confidence)
    return BootstrapResult(
        estimate=estimate,
        ci_low=ci_low,
        ci_high=ci_high,
        confidence=float(confidence),
        n_resamples=resamples,
        method=normalised,
        seed=int(seed),
        n=n,
    )


def bootstrap_paired_ci(
    a: Any,
    b: Any,
    *,
    statistic: Callable[[np.ndarray], float] = np.mean,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = DEFAULT_SEED,
    method: str = "percentile",
) -> BootstrapResult:
    """Subject-level bootstrap CI of the paired difference ``a - b``.

    Complete pairs are resampled with replacement (the pair, i.e. the subject,
    is the resampling unit).  Pairs with a non-finite member are dropped and
    counted in ``result.n``.

    Parameters
    ----------
    a, b:
        Equal-length paired samples (one entry per subject).
    statistic, n_resamples, confidence, seed, method:
        See :func:`bootstrap_ci`.  ``statistic`` is applied to the vector of
        paired differences (default: mean difference).

    Returns
    -------
    BootstrapResult
        ``estimate`` is ``statistic(a - b)`` computed on the observed pairs.
    """
    first = _as_numeric(a, name="a")
    second = _as_numeric(b, name="b")
    if first.size != second.size:
        raise ValueError(f"a and b must have equal length, got {first.size} and {second.size}")
    pairs = np.isfinite(first) & np.isfinite(second)
    if int(pairs.sum()) < 2:
        raise ValueError(
            f"bootstrap_paired_ci requires at least 2 complete finite pairs, got {int(pairs.sum())}"
        )
    differences = first[pairs] - second[pairs]
    result = bootstrap_ci(
        differences,
        statistic=statistic,
        n_resamples=n_resamples,
        confidence=confidence,
        seed=seed,
        method=method,
    )
    logger.debug(
        "bootstrap_paired_ci: %d complete pairs of %d, estimate=%.6g", result.n, first.size, result.estimate
    )
    return result


def _cluster_statistic_interval(
    values: np.ndarray,
    units: np.ndarray,
    statistic: Callable[[np.ndarray], float],
    n_resamples: int,
    confidence: float,
    method: str,
    seed: int,
) -> tuple[float, float, float]:
    normalised, resamples = _validate_settings(
        statistic, n_resamples, confidence, method, seed
    )
    if normalised == "bca":
        raise ValueError("the BCa method is not supported for the cluster bootstrap")
    estimate = _check_statistic(statistic, values)
    unique_units = np.unique(units)
    n_units = int(unique_units.size)
    if n_units < 2:
        raise ValueError(f"cluster bootstrap requires at least 2 units, got {n_units}")
    grouped = [values[units == unit] for unit in unique_units]
    rng = np.random.default_rng(int(seed))
    distribution = np.empty(resamples, dtype=float)
    for index in range(resamples):
        draw = rng.integers(0, n_units, size=n_units)
        sample = np.concatenate([grouped[j] for j in draw])
        distribution[index] = _check_statistic(statistic, sample)
    ci_low, ci_high = _percentile_interval(distribution, confidence)
    return estimate, ci_low, ci_high


def cluster_bootstrap_ci(
    df: pd.DataFrame,
    *,
    unit_col: str,
    value_col: str,
    statistic: Callable[[np.ndarray], float] = np.mean,
    group_cols: Sequence[str] | None = None,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = DEFAULT_SEED,
    method: str = "percentile",
) -> BootstrapResult | pd.DataFrame:
    """Cluster bootstrap for tidy data (resampling whole units).

    Units (e.g. subjects) are resampled with replacement as clusters; all
    rows of a selected unit contribute to the statistic.  This is the correct
    procedure when several observations belong to the same subject.

    Parameters
    ----------
    df:
        Tidy frame.
    unit_col:
        Column identifying the resampling cluster (usually ``subject``).
    value_col:
        Numeric value column.  Rows with non-finite values are dropped.
    statistic:
        Callable mapping the pooled 1-D values of the resampled clusters to a
        scalar.
    group_cols:
        If ``None``, a single :class:`BootstrapResult` is returned.  Otherwise
        one interval is computed per group and a tidy DataFrame with
        ``group_cols + estimate, ci_low, ci_high, confidence, n_resamples,
        method, seed, n`` is returned (``n`` = number of clusters in the
        group).  Child seeds are deterministically derived from ``seed``.
    n_resamples, confidence, seed, method:
        As in :func:`bootstrap_ci`.  ``method="percentile"`` only for the
        grouped variant.

    Returns
    -------
    BootstrapResult or pandas.DataFrame
        See ``group_cols``.
    """
    for column in (unit_col, value_col):
        if column not in df.columns:
            raise ValueError(f"column {column!r} not in DataFrame columns")
    frame = df.loc[:, [c for c in (unit_col, value_col, *(group_cols or ()))]].copy()
    frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
    frame = frame.loc[frame[unit_col].notna()].reset_index(drop=True)
    frame = frame.loc[np.isfinite(frame[value_col].to_numpy(dtype=float))].reset_index(drop=True)
    if frame.empty:
        raise ValueError("cluster_bootstrap_ci: no finite observations")

    if not group_cols:
        estimate, ci_low, ci_high = _cluster_statistic_interval(
            frame[value_col].to_numpy(dtype=float),
            frame[unit_col].to_numpy(),
            statistic,
            n_resamples,
            confidence,
            method,
            seed,
        )
        n_units = int(frame[unit_col].nunique())
        return BootstrapResult(
            estimate=estimate,
            ci_low=ci_low,
            ci_high=ci_high,
            confidence=float(confidence),
            n_resamples=int(n_resamples),
            method=str(method).strip().lower(),
            seed=int(seed),
            n=n_units,
        )

    if str(method).strip().lower() == "bca":
        raise ValueError("the BCa method is not supported for the grouped cluster bootstrap")
    groups = list(group_cols)
    base_rng = np.random.default_rng(int(seed))
    child_seeds = base_rng.integers(0, np.iinfo(np.int64).max, size=len(frame.groupby(groups, dropna=False)))
    rows: list[dict[str, Any]] = []
    for (keys, sub), child_seed in zip(frame.groupby(groups, dropna=False, sort=True), child_seeds):
        estimate, ci_low, ci_high = _cluster_statistic_interval(
            sub[value_col].to_numpy(dtype=float),
            sub[unit_col].to_numpy(),
            statistic,
            n_resamples,
            confidence,
            method,
            int(child_seed),
        )
        record: dict[str, Any] = dict(zip(groups, keys if isinstance(keys, tuple) else (keys,)))
        record.update(
            {
                "estimate": estimate,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "confidence": float(confidence),
                "n_resamples": int(n_resamples),
                "method": "percentile",
                "seed": int(child_seed),
                "n": int(sub[unit_col].nunique()),
            }
        )
        rows.append(record)
    return pd.DataFrame(rows)
