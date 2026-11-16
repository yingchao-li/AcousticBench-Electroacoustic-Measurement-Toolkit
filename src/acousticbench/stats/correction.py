"""Multiple-comparison p-value adjustment.

The experiments test several devices / bands simultaneously, so raw p-values
are adjusted before any significance claim.  Two classical procedures are
implemented:

* **Holm–Bonferroni** (Holm, 1979): controls the family-wise error rate under
  arbitrary dependence, uniformly more powerful than plain Bonferroni.
* **Benjamini–Hochberg** (Benjamini & Hochberg, 1995): controls the false
  discovery rate under independence / positive dependence.

Both return adjusted p-values in the *original* order, are monotone by
construction and capped at 1.  NaN or out-of-range p-values raise
:class:`ValueError`: a silently dropped p-value would distort the family.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from acousticbench.logging_utils import get_logger

__all__ = ["benjamini_hochberg", "holm_bonferroni", "reject"]

logger = get_logger(__name__)


def _validate(p_values: Any) -> np.ndarray:
    array = np.asarray(p_values)
    if array.ndim != 1:
        raise ValueError(f"p_values must be 1-D, got shape {array.shape}")
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"p_values must be numeric, got dtype {array.dtype}")
    values = np.asarray(array, dtype=float)
    if values.size == 0:
        return values
    if not np.all(np.isfinite(values)):
        raise ValueError("p_values must not contain NaN or infinite entries")
    if np.any(values < 0.0) or np.any(values > 1.0):
        raise ValueError("p_values must lie in [0, 1]")
    return values


def holm_bonferroni(p_values: Any) -> np.ndarray:
    """Holm–Bonferroni adjusted p-values.

    Parameters
    ----------
    p_values:
        One-dimensional array of raw p-values in ``[0, 1]``.  NaN is rejected.

    Returns
    -------
    numpy.ndarray
        Adjusted p-values in the original order.  The i-th smallest raw
        p-value is multiplied by ``m - i + 1`` and the sequence is made
        monotone non-decreasing; values are capped at 1.
    """
    p = _validate(p_values)
    m = int(p.size)
    if m == 0:
        return p.copy()
    order = np.argsort(p, kind="stable")
    adjusted_sorted = (m - np.arange(m)) * p[order]
    adjusted_sorted = np.minimum(np.maximum.accumulate(adjusted_sorted), 1.0)
    adjusted = np.empty(m, dtype=float)
    adjusted[order] = adjusted_sorted
    return adjusted


def benjamini_hochberg(p_values: Any) -> np.ndarray:
    """Benjamini–Hochberg adjusted p-values (false discovery rate).

    Parameters
    ----------
    p_values:
        One-dimensional array of raw p-values in ``[0, 1]``.  NaN is rejected.

    Returns
    -------
    numpy.ndarray
        Adjusted p-values in the original order.  With the p-values sorted
        ascending, :math:`\\tilde p_{(i)} = \\min_{j \\ge i}\\left(p_{(j)} m / j\\right)`,
        capped at 1.
    """
    p = _validate(p_values)
    m = int(p.size)
    if m == 0:
        return p.copy()
    order = np.argsort(p, kind="stable")
    ranks = np.arange(1, m + 1)
    adjusted_sorted = p[order] * m / ranks
    # enforce monotonicity from the largest p-value downwards
    adjusted_sorted = np.minimum.accumulate(adjusted_sorted[::-1])[::-1]
    adjusted_sorted = np.minimum(adjusted_sorted, 1.0)
    adjusted = np.empty(m, dtype=float)
    adjusted[order] = adjusted_sorted
    return adjusted


def reject(p_values: Any, alpha: float = 0.05, method: str = "holm") -> np.ndarray:
    """Boolean rejection decisions after multiple-comparison adjustment.

    Parameters
    ----------
    p_values:
        One-dimensional array of raw p-values.
    alpha:
        Family-wise (or false discovery) rate in ``(0, 1)``.
    method:
        ``"holm"`` (default), ``"bh"`` / ``"benjamini_hochberg"``, or
        ``"none"`` for the unadjusted comparison.

    Returns
    -------
    numpy.ndarray
        Boolean array of the same length as ``p_values``.
    """
    if not 0.0 < float(alpha) < 1.0:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha!r}")
    normalised = str(method).strip().lower()
    p = _validate(p_values)
    if normalised in {"holm", "holm-bonferroni", "holm_bonferroni"}:
        adjusted = holm_bonferroni(p)
    elif normalised in {"bh", "benjamini-hochberg", "benjamini_hochberg", "fdr"}:
        adjusted = benjamini_hochberg(p)
    elif normalised in {"none", "raw", "unadjusted"}:
        adjusted = p
    else:
        raise ValueError(
            f"unknown correction method {method!r}; expected 'holm', 'bh' or 'none'"
        )
    return adjusted <= float(alpha)
