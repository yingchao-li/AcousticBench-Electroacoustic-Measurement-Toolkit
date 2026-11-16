"""Small analysis utilities shared by the experiments."""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from acousticbench.data.dataset import TransferCube
from acousticbench.stats.bands import Band

__all__ = [
    "band_summary",
    "mean_ci",
    "nearest_frequency",
    "percentile_curves",
    "subject_means",
    "summarize_subjects",
]


def nearest_frequency(frequencies_hz: np.ndarray, target_hz: float) -> float:
    """Frequency bin of a uniform grid that is closest to ``target_hz``."""
    index = int(np.argmin(np.abs(np.asarray(frequencies_hz) - float(target_hz))))
    return float(np.asarray(frequencies_hz)[index])


def percentile_curves(
    cube: TransferCube,
    *,
    reference: float = 1.0,
    quantiles: Sequence[float] = (0.1, 0.25, 0.5, 0.75, 0.9),
    frequency_min: float = 50.0,
    frequency_max: float = 20000.0,
) -> pd.DataFrame:
    """Across-subject percentile curves per device.

    Parameters
    ----------
    cube:
        Complex transfer cube or level cube.
    reference:
        Reference value for level conversion (e.g. ``20e-6`` for dB SPL).
    quantiles:
        Quantiles to compute across all valid subject × reinsertion values.
    """
    levels = cube.level_array(reference=reference)
    freqs = cube.freq_hz
    keep = (freqs >= frequency_min) & (freqs <= frequency_max)
    frames = []
    for device_index, device in enumerate(cube.devices):
        data = levels[keep, device_index, :, :].reshape(int(keep.sum()), -1)
        with np.errstate(invalid="ignore"):
            quantile_values = np.nanpercentile(data, [q * 100 for q in quantiles], axis=1)
        frame = pd.DataFrame(
            {
                "frequency_hz": freqs[keep],
                "device_code": device.code,
                "device": device.label,
                "family": device.family,
                "family_label": device.family_label,
                "condition": device.condition.value if device.condition else None,
                "n_valid": np.sum(np.isfinite(data), axis=1),
            }
        )
        for quantile, values in zip(quantiles, quantile_values):
            frame[f"q{int(round(quantile * 100)):02d}"] = values
        frame = frame.rename(columns={"q50": "median_db"})
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def band_summary(
    band_frame: pd.DataFrame,
    *,
    value_col: str = "level_db",
    group_cols: Sequence[str] = (
        "family",
        "family_label",
        "band",
        "band_center_hz",
    ),
    include_quantiles: bool = True,
) -> pd.DataFrame:
    """Summarise a tidy band-level frame across subjects/reinsertions."""
    grouped = band_frame.loc[band_frame["valid"]].groupby(list(group_cols), as_index=False)
    summary = grouped.agg(
        median_db=(value_col, "median"),
        mean_db=(value_col, "mean"),
        sd_db=(value_col, "std"),
        n=(value_col, "size"),
    )
    if include_quantiles:
        q25 = (
            grouped[value_col]
            .quantile(0.25)
            .reset_index()
            .rename(columns={value_col: "q25_db"})
        )
        q75 = (
            grouped[value_col]
            .quantile(0.75)
            .reset_index()
            .rename(columns={value_col: "q75_db"})
        )
        summary = summary.merge(q25, on=list(group_cols), how="left").merge(
            q75, on=list(group_cols), how="left"
        )
    return summary


def subject_means(
    frame: pd.DataFrame,
    *,
    value_col: str,
    group_cols: Sequence[str],
) -> pd.DataFrame:
    """Collapse reinsertions to one value per subject (mean over valid repeats)."""
    columns = list(dict.fromkeys([*group_cols, "subject"]))
    collapsed = (
        frame.loc[frame["valid"]]
        .groupby(columns, as_index=False)[value_col]
        .mean()
        .rename(columns={value_col: "subject_mean"})
    )
    return collapsed


def mean_ci(
    frame: pd.DataFrame,
    *,
    value_col: str,
    group_cols: Sequence[str],
    confidence: float = 0.95,
) -> pd.DataFrame:
    """Mean and Student-t confidence interval across *subjects*.

    The frame is expected to contain a ``subject`` column; reinsertions should
    already be collapsed (see :func:`subject_means`), but the function is
    robust to duplicates by averaging them first.
    """
    group_cols = list(group_cols)
    collapsed = subject_means(frame, value_col=value_col, group_cols=group_cols)
    rows = []
    for key, group in collapsed.groupby(group_cols, as_index=False):
        values = group["subject_mean"].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        n = values.size
        row = {column: value for column, value in zip(group_cols, key)} if len(group_cols) > 1 else {
            group_cols[0]: key[0] if isinstance(key, tuple) else key
        }
        if n == 0:
            row.update(n=0, mean_db=np.nan, sd_db=np.nan, se_db=np.nan, ci_low_db=np.nan, ci_high_db=np.nan)
            rows.append(row)
            continue
        mean = float(np.mean(values))
        sd = float(np.std(values, ddof=1)) if n > 1 else float("nan")
        se = sd / np.sqrt(n) if n > 1 else float("nan")
        if n > 1:
            half_width = float(stats.t.ppf(0.5 + confidence / 2.0, n - 1) * se)
        else:
            half_width = float("nan")
        row.update(
            n=n,
            mean_db=mean,
            sd_db=sd,
            se_db=se,
            ci_low_db=mean - half_width,
            ci_high_db=mean + half_width,
        )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_subjects(
    frame: pd.DataFrame,
    *,
    value_col: str,
    group_cols: Sequence[str],
    confidence: float = 0.95,
) -> pd.DataFrame:
    """Alias of :func:`mean_ci` for readability in experiments."""
    return mean_ci(
        frame, value_col=value_col, group_cols=group_cols, confidence=confidence
    )


def band_labels(bands: Iterable[Band]) -> list[str]:
    return [band.label for band in bands]
