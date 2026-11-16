"""Plotting helpers shared by experiments and reports.

Matplotlib only (no seaborn); Agg backend; deterministic style.  Colours are
consistent across all figures and the dashboard/PDF report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

__all__ = [
    "FAMILY_COLORS",
    "FAMILY_LABELS",
    "band_bar_plot",
    "curves_plot",
    "forest_plot",
    "heatmap_plot",
    "save_figure",
    "scatter_identity_plot",
    "set_style",
]

FAMILY_LABELS = {
    "closed_earmold": "Closed Earmold",
    "vented_earmold": "Vented Earmold",
    "nugget_earmold": "Nugget Earmold",
    "silicone_earmold": "Silicone Earmold",
    "open_dome": "Open Dome",
    "tulip_dome": "Tulip Dome",
    "power_dome": "Power Dome",
    "open_ear": "Open Ear",
    "free_field": "Free Field",
}

FAMILY_COLORS = {
    "closed_earmold": "#1f77b4",
    "vented_earmold": "#17becf",
    "nugget_earmold": "#d62728",
    "silicone_earmold": "#9467bd",
    "open_dome": "#2ca02c",
    "tulip_dome": "#ff7f0e",
    "power_dome": "#8c564b",
    "open_ear": "#7f7f7f",
    "free_field": "#bcbd22",
}


def set_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 7.5,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "lines.linewidth": 1.6,
            "figure.autolayout": False,
            "mathtext.default": "regular",
        }
    )


set_style()


def save_figure(figure: plt.Figure, path: str | Path, dpi: int = 150) -> Path:
    """Save and close a figure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(figure)
    return path


def _color(key: str) -> str:
    return FAMILY_COLORS.get(key, "#333333")


def curves_plot(
    frame: pd.DataFrame,
    *,
    x_col: str,
    y_col: str,
    hue_col: str,
    ax: plt.Axes | None = None,
    title: str = "",
    xlabel: str = "Frequency [Hz]",
    ylabel: str = "",
    log_x: bool = True,
    alpha: float = 0.9,
    linewidth: float = 1.8,
    label_hook=lambda key: FAMILY_LABELS.get(str(key), str(key)),
    y_reference: float | None = None,
    x_limits: tuple[float, float] | None = None,
    y_limits: tuple[float, float] | None = None,
) -> plt.Axes:
    """Plot one curve per hue value using the shared colour map."""
    if ax is None:
        _, ax = plt.subplots(figsize=(7.0, 3.8))
    for key, group in frame.groupby(hue_col, sort=False):
        group = group.sort_values(x_col)
        ax.plot(
            group[x_col],
            group[y_col],
            label=label_hook(key),
            color=_color(str(key)),
            alpha=alpha,
            linewidth=linewidth,
        )
    if log_x:
        ax.set_xscale("log")
    if x_limits is not None:
        ax.set_xlim(*x_limits)
    if y_limits is not None:
        ax.set_ylim(*y_limits)
    if y_reference is not None:
        ax.axhline(y_reference, color="k", linewidth=0.8, linestyle="--")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.legend(loc="best", frameon=False, ncol=2)
    return ax


def band_bar_plot(
    frame: pd.DataFrame,
    *,
    band_col: str,
    value_col: str,
    hue_col: str,
    ax: plt.Axes | None = None,
    title: str = "",
    ylabel: str = "dB",
    y_reference: float | None = 0.0,
    label_hook=lambda key: FAMILY_LABELS.get(str(key), str(key)),
) -> plt.Axes:
    """Grouped bar chart per band (power-of-visual-hierarchy friendly)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(9.0, 4.0))
    pivot = frame.pivot_table(
        index=band_col, columns=hue_col, values=value_col, aggfunc="median"
    )
    order = [band for band in frame[band_col].drop_duplicates() if band in pivot.index]
    pivot = pivot.reindex(order)
    x = np.arange(len(pivot.index))
    n_series = max(1, pivot.shape[1])
    width = 0.8 / n_series
    for series_index, column in enumerate(pivot.columns):
        ax.bar(
            x + (series_index - (n_series - 1) / 2) * width,
            pivot[column].to_numpy(dtype=float),
            width=width,
            color=_color(str(column)),
            label=label_hook(column),
        )
    ax.set_xticks(x, [str(index) for index in pivot.index], rotation=0)
    if y_reference is not None:
        ax.axhline(y_reference, color="k", linewidth=0.8)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.legend(frameon=False, ncol=min(4, n_series))
    return ax


def heatmap_plot(
    frame: pd.DataFrame,
    *,
    index_col: str,
    columns_col: str,
    value_col: str,
    ax: plt.Axes | None = None,
    title: str = "",
    cmap: str = "RdBu_r",
    center: float | None = 0.0,
    xlabel: str = "",
    ylabel: str = "",
    colorbar_label: str = "",
    fmt: str = ".1f",
    annotate: bool = True,
) -> plt.Axes:
    """Annotated heatmap with a divergent colour map by default."""
    if ax is None:
        _, ax = plt.subplots(figsize=(9.0, 4.2))
    pivot = frame.pivot_table(
        index=index_col, columns=columns_col, values=value_col, aggfunc="median"
    )
    image = ax.imshow(
        pivot.to_numpy(dtype=float),
        aspect="auto",
        cmap=cmap,
        vmin=None if center is None else -np.nanmax(np.abs(pivot.to_numpy(dtype=float))) + center,
        vmax=None if center is None else np.nanmax(np.abs(pivot.to_numpy(dtype=float))) + center,
    )
    ax.set_xticks(np.arange(pivot.shape[1]), [str(c) for c in pivot.columns])
    ax.set_yticks(np.arange(pivot.shape[0]), [str(i) for i in pivot.index])
    ax.grid(False)
    if annotate:
        values = pivot.to_numpy(dtype=float)
        threshold = np.nanmax(np.abs(values)) / 2 if np.isfinite(values).any() else 0
        for row in range(values.shape[0]):
            for column in range(values.shape[1]):
                value = values[row, column]
                if np.isfinite(value):
                    ax.text(
                        column,
                        row,
                        format(value, fmt),
                        ha="center",
                        va="center",
                        fontsize=6.5,
                        color="white" if abs(value) > threshold else "black",
                    )
    if title:
        ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    colorbar = ax.figure.colorbar(image, ax=ax, shrink=0.9)
    if colorbar_label:
        colorbar.set_label(colorbar_label)
    return ax


def forest_plot(
    frame: pd.DataFrame,
    *,
    estimate_col: str,
    low_col: str,
    high_col: str,
    label_col: str,
    ax: plt.Axes | None = None,
    title: str = "",
    xlabel: str = "Effect [dB]",
    reference: float = 0.0,
    color_by: str | None = None,
) -> plt.Axes:
    """Forest plot with 95 % confidence intervals."""
    if ax is None:
        height = max(2.4, 0.42 * len(frame) + 1.2)
        _, ax = plt.subplots(figsize=(7.0, height))
    y = np.arange(len(frame))
    colors = (
        [_color(str(value)) for value in frame[color_by]] if color_by else ["#1f77b4"] * len(frame)
    )
    ax.errorbar(
        frame[estimate_col],
        y,
        xerr=[
            frame[estimate_col] - frame[low_col],
            frame[high_col] - frame[estimate_col],
        ],
        fmt="o",
        color="none",
        ecolor="#333333",
        elinewidth=1.2,
        capsize=3,
    )
    ax.scatter(frame[estimate_col], y, c=colors, s=28, zorder=3)
    ax.axvline(reference, color="k", linewidth=0.8)
    ax.set_yticks(y, [str(label) for label in frame[label_col]])
    ax.set_xlabel(xlabel)
    if title:
        ax.set_title(title)
    ax.invert_yaxis()
    return ax


def scatter_identity_plot(
    frame: pd.DataFrame,
    *,
    x_col: str,
    y_col: str,
    label_col: str | None = None,
    ax: plt.Axes | None = None,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    color_by: str | None = None,
    unit: str = "",
) -> plt.Axes:
    """Scatter with identity line and annotated deviations."""
    if ax is None:
        _, ax = plt.subplots(figsize=(5.2, 4.6))
    colors = (
        [_color(str(value)) for value in frame[color_by]] if color_by else "#1f77b4"
    )
    ax.scatter(frame[x_col], frame[y_col], c=colors, s=26, alpha=0.9)
    if len(frame) and np.isfinite(frame[[x_col, y_col]].to_numpy(dtype=float)).any():
        limits = [
            min(np.nanmin(frame[x_col]), np.nanmin(frame[y_col])),
            max(np.nanmax(frame[x_col]), np.nanmax(frame[y_col])),
        ]
        ax.plot(limits, limits, "k--", linewidth=0.8)
        ax.set_xlim(limits)
        ax.set_ylim(limits)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    if label_col is not None:
        for _, row in frame.iterrows():
            ax.annotate(
                str(row[label_col]),
                (row[x_col], row[y_col]),
                fontsize=6,
                xytext=(3, 3),
                textcoords="offset points",
            )
    return ax
