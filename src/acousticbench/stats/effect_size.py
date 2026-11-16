"""Effect sizes for paired and independent samples.

The formulas follow the standard references:

* Cohen's :math:`d_z` for paired differences: :math:`\\bar d / s_d` with
  :math:`s_d` using ``ddof=1`` (Cohen, 1988).
* Cohen's :math:`d` for independent samples with pooled standard deviation.
* Hedges' :math:`g`: :math:`d_z \\cdot (1 - 3 / (4\\,df - 1))` with
  :math:`df = n - 1` (Hedges, 1981).
* Rank-biserial correlation for the Wilcoxon signed-rank test:
  :math:`(W_+ - W_-) / (W_+ + W_-)` (Cureton, 1956; Kerby, 2014).

NaN entries are excluded before the computation.  A zero standard deviation
makes a standardised effect size undefined; :class:`ValueError` is raised
instead of returning a fabricated (infinite) number.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import scipy.stats as st

from acousticbench.logging_utils import get_logger

__all__ = ["cohen_d", "cohen_dz", "hedges_g", "rank_biserial"]

logger = get_logger(__name__)


def _clean(values: Any, *, name: str) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim == 0:
        raise ValueError(f"{name} must be a sequence, got a scalar")
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"{name} must be numeric, got dtype {array.dtype}")
    array = np.asarray(array, dtype=float).ravel()
    return array[np.isfinite(array)]


def cohen_dz(differences: Any) -> float:
    """Cohen's :math:`d_z` for paired differences.

    Parameters
    ----------
    differences:
        Paired differences ``a - b`` (one entry per subject).  Non-finite
        entries are excluded.

    Returns
    -------
    float
        :math:`\\bar d / s_d` with the sample standard deviation
        (``ddof=1``).

    Raises
    ------
    ValueError
        If fewer than two finite differences remain or the standard deviation
        is zero (the effect size is then undefined).
    """
    data = _clean(differences, name="differences")
    n = int(data.size)
    if n < 2:
        raise ValueError(f"cohen_dz requires at least 2 finite paired differences, got {n}")
    sd = float(np.std(data, ddof=1))
    if not np.isfinite(sd) or sd == 0.0:
        raise ValueError("cohen_dz is undefined: the paired differences have zero variance")
    return float(np.mean(data) / sd)


def cohen_d(a: Any, b: Any) -> float:
    """Cohen's :math:`d` for two independent samples (pooled SD).

    Parameters
    ----------
    a, b:
        Independent numeric samples.  Non-finite entries are excluded.

    Returns
    -------
    float
        ``(mean_a - mean_b) / s_pooled`` with

        .. math::
            s_{pooled} = \\sqrt{\\frac{(n_a-1)s_a^2 + (n_b-1)s_b^2}
                                        {n_a + n_b - 2}}.
    """
    first = _clean(a, name="a")
    second = _clean(b, name="b")
    n_a, n_b = int(first.size), int(second.size)
    if n_a < 2 or n_b < 2:
        raise ValueError(
            f"cohen_d requires at least 2 finite values per sample, got {n_a} and {n_b}"
        )
    df = n_a + n_b - 2
    pooled_var = ((n_a - 1) * np.var(first, ddof=1) + (n_b - 1) * np.var(second, ddof=1)) / df
    if not np.isfinite(pooled_var) or pooled_var <= 0.0:
        raise ValueError("cohen_d is undefined: the pooled standard deviation is zero")
    return float((np.mean(first) - np.mean(second)) / np.sqrt(pooled_var))


def hedges_g(differences: Any) -> float:
    """Hedges' :math:`g` (small-sample-corrected Cohen's :math:`d_z`).

    Parameters
    ----------
    differences:
        Paired differences ``a - b``.  Non-finite entries are excluded.

    Returns
    -------
    float
        :math:`d_z \\cdot (1 - 3/(4\\,df - 1))` with :math:`df = n - 1`.
    """
    data = _clean(differences, name="differences")
    n = int(data.size)
    if n < 2:
        raise ValueError(f"hedges_g requires at least 2 finite paired differences, got {n}")
    dz = cohen_dz(data)
    df = n - 1
    correction = 1.0 - 3.0 / (4.0 * df - 1.0)
    return float(dz * correction)


def rank_biserial(differences: Any) -> float:
    """Rank-biserial correlation of the Wilcoxon signed-rank test.

    Parameters
    ----------
    differences:
        Paired differences ``a - b``.  Non-finite entries are excluded.  Exact
        zero differences are ignored (matching the ``zero_method="wilcox"``
        convention of the signed-rank test).

    Returns
    -------
    float
        ``(W_+ - W_-) / (W_+ + W_-)`` where ``W_+`` and ``W_-`` are the sums
        of the average ranks of the absolute non-zero differences with
        positive and negative sign respectively.  The result lies in
        ``[-1, 1]``.  If all differences are exactly zero the effect size is
        undefined and ``0.0`` is returned together with a logged warning.
    """
    data = _clean(differences, name="differences")
    nonzero = data[data != 0.0]
    if nonzero.size == 0:
        logger.warning("rank_biserial: all differences are zero; returning 0.0")
        return 0.0
    ranks = st.rankdata(np.abs(nonzero), method="average")
    positive = float(np.sum(ranks[nonzero > 0.0]))
    negative = float(np.sum(ranks[nonzero < 0.0]))
    total = positive + negative
    return float((positive - negative) / total) if total > 0.0 else 0.0
