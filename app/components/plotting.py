"""Plotly helpers with a consistent AcousticBench chart style.

All figures use the same template, colours, typography and a logarithmic
frequency axis where a frequency axis is present.  Helpers accept tidy
(tidy/long) pandas frames so the pages stay free of plotting boilerplate.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from acousticbench.report.figures import FAMILY_COLORS, FAMILY_LABELS

__all__ = [
    "COLORWAY",
    "PLOTLY_TEMPLATE",
    "band_bar_figure",
    "curves_figure",
    "empty_state_figure",
    "heatmap_figure",
    "log_x_axis",
    "spectrum_figure",
    "stft_figure",
    "style_figure",
    "time_series_figure",
]

#: Default colour sequence used for non-family series.
COLORWAY: tuple[str, ...] = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#7f7f7f",
)

PLOTLY_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        colorway=list(COLORWAY),
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=12, color="#1e2a33"),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=58, r=24, t=52, b=52),
        title=dict(font=dict(size=15, color="#1e2a33"), x=0.01, xanchor="left"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=10)),
        xaxis=dict(
            gridcolor="#e7edf2",
            zerolinecolor="#c9d3dc",
            linecolor="#9fb3c8",
            tickfont=dict(size=10),
            title_font=dict(size=11),
        ),
        yaxis=dict(
            gridcolor="#e7edf2",
            zerolinecolor="#c9d3dc",
            linecolor="#9fb3c8",
            tickfont=dict(size=10),
            title_font=dict(size=11),
        ),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#c9d3dc", font=dict(size=11)),
    )
)


def _family_colour(key: str, fallback_index: int = 0) -> str:
    if key in FAMILY_COLORS:
        return FAMILY_COLORS[key]
    return COLORWAY[fallback_index % len(COLORWAY)]


def family_colour(key: str, fallback_index: int = 0) -> str:
    """Public colour accessor for a family key (stable across all pages)."""
    return _family_colour(str(key), fallback_index)


def family_label(key: str) -> str:
    """Public display label for a family key."""
    return _family_label(str(key))


def _family_label(key: str) -> str:
    return FAMILY_LABELS.get(str(key), str(key))


def style_figure(
    figure: go.Figure,
    *,
    title: str = "",
    x_title: str = "",
    y_title: str = "",
    height: int = 430,
    legend: bool = True,
) -> go.Figure:
    """Apply the shared template and axis labels to a figure."""
    figure.update_layout(template=PLOTLY_TEMPLATE, height=height, title=title)
    if x_title:
        figure.update_xaxes(title_text=x_title)
    if y_title:
        figure.update_yaxes(title_text=y_title)
    figure.update_layout(showlegend=legend)
    return figure


def log_x_axis(figure: go.Figure, *, limits: tuple[float, float] | None = None) -> go.Figure:
    """Switch the x axis to a logarithmic frequency axis."""
    figure.update_xaxes(type="log")
    if limits is not None:
        low, high = limits
        figure.update_xaxes(range=[float(np.log10(low)), float(np.log10(high))])
    return figure


def empty_state_figure(message: str, *, height: int = 260) -> go.Figure:
    """Figure used to display an empty/missing-data state instead of a crash."""
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=13, color="#5b6770"),
        align="center",
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return style_figure(figure, height=height, legend=False)


def curves_figure(
    frame: pd.DataFrame,
    *,
    x: str,
    y: str,
    series: str,
    dash: str | None = None,
    title: str = "",
    x_title: str = "Frequency [Hz]",
    y_title: str = "",
    log_x: bool = True,
    height: int = 430,
    line_width: float = 1.8,
    y_reference: float | None = None,
    a_series: str = "",
) -> go.Figure:
    """Line plot with one trace per series value (optionally dashed by a second key)."""
    figure = go.Figure()
    if frame is None or frame.empty:
        return empty_state_figure("No data for the current selection", height=height)
    groups: Iterable[tuple[object, pd.DataFrame]]
    if dash is not None and dash in frame.columns:
        groups = frame.groupby([series, dash], sort=False, dropna=False)
        dash_styles = ["solid", "dash", "dot", "dashdot"]
        dash_keys = list(pd.unique(frame[dash]))
        for offset, ((series_value, dash_value), group) in enumerate(groups):
            group = group.sort_values(x)
            family_key = str(series_value)
            dash_style = dash_styles[dash_keys.index(dash_value) % len(dash_styles)]
            figure.add_trace(
                go.Scatter(
                    x=group[x],
                    y=group[y],
                    mode="lines",
                    name=f"{_family_label(family_key)} \u00b7 {dash_value}",
                    line=dict(color=_family_colour(family_key, offset), width=line_width, dash=dash_style),
                    hovertemplate="%{x:.4g} Hz<br>%{y:.2f} dB<extra></extra>",
                )
            )
    else:
        for offset, (series_value, group) in enumerate(frame.groupby(series, sort=False, dropna=False)):
            group = group.sort_values(x)
            family_key = str(series_value)
            figure.add_trace(
                go.Scatter(
                    x=group[x],
                    y=group[y],
                    mode="lines",
                    name=_family_label(family_key),
                    line=dict(color=_family_colour(family_key, offset), width=line_width),
                    hovertemplate="%{x:.4g} Hz<br>%{y:.2f} dB<extra></extra>",
                )
            )
    if y_reference is not None:
        figure.add_hline(y=float(y_reference), line_dash="dash", line_color="#5b6770", line_width=1)
    if log_x:
        log_x_axis(figure)
    return style_figure(figure, title=title, x_title=x_title, y_title=y_title, height=height)


def band_bar_figure(
    frame: pd.DataFrame,
    *,
    band: str,
    value: str,
    series: str,
    title: str = "",
    x_title: str = "",
    y_title: str = "dB",
    height: int = 430,
    y_reference: float | None = 0.0,
) -> go.Figure:
    """Grouped bar chart of band values with one bar series per group."""
    figure = go.Figure()
    if frame is None or frame.empty:
        return empty_state_figure("No band data for the current selection", height=height)
    order = list(pd.unique(frame[band]))
    for offset, (series_value, group) in enumerate(frame.groupby(series, sort=False, dropna=False)):
        indexed = group.set_index(band).reindex(order)
        figure.add_trace(
            go.Bar(
                x=order,
                y=indexed[value].to_numpy(dtype=float),
                name=_family_label(str(series_value)),
                marker_color=_family_colour(str(series_value), offset),
                hovertemplate="%{x}<br>%{y:.2f} dB<extra></extra>",
            )
        )
    if y_reference is not None:
        figure.add_hline(y=float(y_reference), line_dash="dash", line_color="#5b6770", line_width=1)
    figure.update_layout(barmode="group")
    return style_figure(figure, title=title, x_title=x_title, y_title=y_title, height=height)


def heatmap_figure(
    frame: pd.DataFrame,
    *,
    index: str,
    columns: str,
    value: str,
    title: str = "",
    x_title: str = "",
    y_title: str = "",
    colorbar_title: str = "dB",
    height: int = 460,
    colorscale: str = "RdBu_r",
    zmid: float | None = 0.0,
    aggregator: str = "median",
) -> go.Figure:
    """Annotated heatmap from a tidy frame (pivot + heatmap)."""
    if frame is None or frame.empty:
        return empty_state_figure("No data for the current heatmap", height=height)
    pivot = frame.pivot_table(index=index, columns=columns, values=value, aggfunc=aggregator)
    if pivot.empty:
        return empty_state_figure("No data for the current heatmap", height=height)
    figure = go.Figure(
        data=go.Heatmap(
            z=pivot.to_numpy(dtype=float),
            x=[str(item) for item in pivot.columns],
            y=[str(item) for item in pivot.index],
            colorscale=colorscale,
            zmid=zmid,
            colorbar=dict(title=dict(text=colorbar_title, side="right"), thickness=12),
            hovertemplate="%{y}<br>%{x}<br>%{z:.2f}<extra></extra>",
        )
    )
    values = pivot.to_numpy(dtype=float)
    if np.isfinite(values).any() and values.size <= 200:
        figure.add_trace(
            go.Scatter(
                x=np.tile(np.arange(values.shape[1]), values.shape[0]),
                y=np.repeat(np.arange(values.shape[0]), values.shape[1]),
                mode="text",
                text=[
                    f"{value:.1f}" if np.isfinite(value) else ""
                    for value in values.reshape(-1)
                ],
                textfont=dict(size=9, color="#22303c"),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        figure.update_xaxes(tickmode="array", tickvals=list(range(values.shape[1])), ticktext=[str(c) for c in pivot.columns])
        figure.update_yaxes(tickmode="array", tickvals=list(range(values.shape[0])), ticktext=[str(i) for i in pivot.index])
    return style_figure(figure, title=title, x_title=x_title, y_title=y_title, height=height)


def time_series_figure(
    time_s: np.ndarray,
    series: dict[str, np.ndarray],
    *,
    title: str = "",
    y_title: str = "Amplitude",
    height: int = 360,
) -> go.Figure:
    """Multi-trace time waveform figure."""
    figure = go.Figure()
    for offset, (name, values) in enumerate(series.items()):
        figure.add_trace(
            go.Scatter(
                x=np.asarray(time_s),
                y=np.asarray(values),
                mode="lines",
                name=name,
                line=dict(color=COLORWAY[offset % len(COLORWAY)], width=1.2),
            )
        )
    return style_figure(figure, title=title, x_title="Time [s]", y_title=y_title, height=height)


def spectrum_figure(
    frequencies_hz: np.ndarray,
    series: dict[str, np.ndarray],
    *,
    title: str = "",
    y_title: str = "Magnitude [dB]",
    height: int = 380,
) -> go.Figure:
    """Line figure of one-sided spectra on a logarithmic frequency axis."""
    figure = go.Figure()
    for offset, (name, values) in enumerate(series.items()):
        figure.add_trace(
            go.Scatter(
                x=np.asarray(frequencies_hz),
                y=np.asarray(values),
                mode="lines",
                name=name,
                line=dict(color=COLORWAY[offset % len(COLORWAY)], width=1.2),
            )
        )
    log_x_axis(figure)
    return style_figure(figure, title=title, x_title="Frequency [Hz]", y_title=y_title, height=height)


def stft_figure(
    frequencies_hz: np.ndarray,
    times_s: np.ndarray,
    magnitude_db: np.ndarray,
    *,
    title: str = "STFT magnitude",
    height: int = 380,
) -> go.Figure:
    """Spectrogram heatmap of an STFT magnitude matrix."""
    figure = go.Figure(
        data=go.Heatmap(
            z=np.asarray(magnitude_db),
            x=np.asarray(times_s),
            y=np.asarray(frequencies_hz),
            colorscale="Viridis",
            colorbar=dict(title=dict(text="dB", side="right"), thickness=12),
            hovertemplate="t=%{x:.3f} s<br>f=%{y:.0f} Hz<br>%{z:.1f} dB<extra></extra>",
        )
    )
    figure.update_yaxes(type="log")
    return style_figure(figure, title=title, x_title="Time [s]", y_title="Frequency [Hz]", height=height, legend=False)


def download_frame_button(frame: pd.DataFrame, filename: str, label: str = "Download CSV") -> None:
    """Render a CSV download button for a DataFrame (kept here for reuse)."""
    import streamlit as st

    if frame is None or frame.empty:
        return
    st.download_button(
        label=label,
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        width="content",
    )
