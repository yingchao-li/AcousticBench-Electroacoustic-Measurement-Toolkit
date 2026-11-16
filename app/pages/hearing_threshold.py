"""Page 5 — Hearing Threshold.

Audiograms per family/condition, the threshold probe-tube presence effect
(ΔT), and the threshold-versus-coupling comparison, plus the persisted E07
result summary.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from acousticbench.measurements.ptpe import ptpe_threshold_db
from acousticbench.measurements.threshold import (
    threshold_curve,
    threshold_table,
)
from acousticbench.types import DEVICES, Condition
from app.components import filters, plotting, theme, ui
from app.components.data import result_for

TITLE = "Hearing Threshold"
SUBTITLE = (
    "Hearing thresholds measured with the hearing-aid driver (dBV at 125\u20132000 Hz), the "
    "\u0394T probe-tube presence effect and the effect of earpiece coupling."
)

_COUPLING_BY_CODE = {device.code: device.coupling for device in DEVICES}
_COUPLING_LABELS = {"earmold": "Earmold", "dome": "Dome", "open": "Open ear"}


def _audiogram_frame(dataset, conditions, families) -> pd.DataFrame:
    frame, error = ui.safe_call(
        threshold_curve,
        dataset,
        conditions=conditions or None,
        families=families or None,
    )
    if error is not None or frame is None:
        return pd.DataFrame()
    conditions_map = {
        "reference": "Reference",
        "measurement": "Measurement",
    }
    frame = frame.copy()
    frame["condition_label"] = frame["condition"].map(conditions_map).fillna(frame["condition"])
    return frame


def _delta_t_frame(dataset, families) -> pd.DataFrame:
    cube, error = ui.safe_call(ptpe_threshold_db, dataset)
    if error is not None or cube is None:
        return pd.DataFrame()
    levels = cube.level_array()
    frames = []
    for device_index, device in enumerate(cube.devices):
        if families and device.family not in set(families):
            continue
        with np.errstate(invalid="ignore"):
            median = np.nanmedian(levels[:, device_index, :, :], axis=(1, 2))
        frames.append(
            pd.DataFrame(
                {
                    "family": device.family,
                    "family_label": device.family_label,
                    "frequency_hz": np.asarray(cube.freq_hz, dtype=float),
                    "median_delta_t_db": median,
                }
            )
        )
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).dropna(subset=["median_delta_t_db"])


def _threshold_vs_coupling(dataset, conditions, families) -> pd.DataFrame:
    table, error = ui.safe_call(
        threshold_table,
        dataset,
        conditions=conditions or None,
        families=families or None,
    )
    if error is not None or table is None or table.empty:
        return pd.DataFrame()
    table = table.copy()
    table["coupling"] = table["device_code"].map(
        lambda code: _COUPLING_BY_CODE[int(code)].value
    )
    table["coupling_label"] = table["coupling"].map(_COUPLING_LABELS).fillna(table["coupling"])
    subject_level = (
        table.groupby(["subject", "threshold_frequency_hz", "coupling_label"], as_index=False)[
            "threshold_dbv"
        ]
        .median()
    )
    return subject_level


def render() -> None:
    """Render the Hearing Threshold page."""
    theme.page_header(TITLE, SUBTITLE, eyebrow="Audiometry")
    dataset = ui.ensure_dataset()
    if dataset is None:
        return

    st.sidebar.markdown("### Threshold filters")
    conditions = filters.condition_widget("thr", default=(Condition.MEASUREMENT, Condition.REFERENCE))
    families = filters.families_widget("thr")

    audiogram = _audiogram_frame(dataset, conditions, families)
    theme.metric_cards(
        [
            ("Audiometric frequencies", str(dataset.threshold_frequency_hz.size), None),
            ("Families", str(audiogram["family"].nunique() if not audiogram.empty else 0), None),
            ("Conditions", str(audiogram["condition"].nunique() if not audiogram.empty else 0), None),
            (
                "Median threshold",
                f"{audiogram['median_dbv'].median():.1f} dBV" if not audiogram.empty else "\u2014",
                "Median over families, frequencies and conditions.",
            ),
        ]
    )

    tabs = st.tabs(["Audiograms", "Delta T (PTPE)", "Threshold vs coupling"])
    with tabs[0]:
        theme.section_title(
            "Audiograms per family and condition",
            "Median threshold voltage across subjects and reinsertions. Lower dBV means a more "
            "sensitive coupling (less receiver voltage is needed at threshold).",
        )
        if audiogram.empty:
            st.info("No valid threshold data for the current selection.")
        else:
            figure = go.Figure()
            dash_styles = ["solid", "dash", "dot"]
            condition_order = list(pd.unique(audiogram["condition_label"]))
            for family_index, (family, group) in enumerate(
                audiogram.groupby("family", sort=False)
            ):
                for condition_index, (condition_label, condition_group) in enumerate(
                    group.groupby("condition_label", sort=False)
                ):
                    condition_group = condition_group.sort_values("frequency_hz")
                    figure.add_trace(
                        go.Scatter(
                            x=condition_group["frequency_hz"],
                            y=condition_group["median_dbv"],
                            mode="lines+markers",
                            name=f"{plotting.family_label(str(family))} \u00b7 {condition_label}",
                            line=dict(
                                color=plotting.family_colour(str(family), family_index),
                                width=1.8,
                                dash=dash_styles[condition_index % len(dash_styles)],
                            ),
                            marker=dict(size=6),
                            hovertemplate="%{x:.4g} Hz<br>%{y:.2f} dBV<extra></extra>",
                        )
                    )
            figure.update_xaxes(type="log", title_text="Frequency [Hz]")
            figure.update_yaxes(title_text="Threshold [dBV]", autorange="reversed")
            figure.update_layout(
                template=plotting.PLOTLY_TEMPLATE,
                title="Median hearing threshold (lower dBV = more sensitive)",
                height=450,
            )
            st.plotly_chart(figure, width="stretch")
            st.dataframe(audiogram, width="stretch", hide_index=True, height=360)
            ui.download_frame(audiogram, "threshold_curves_filtered.csv", "Download audiogram data (CSV)")

    with tabs[1]:
        theme.section_title(
            "\u0394T threshold probe-tube presence effect",
            "Delta T = T(reference) \u2212 T(measurement). Negative values indicate that a "
            "higher receiver voltage is required at threshold with the measurement probe in place.",
        )
        delta = _delta_t_frame(dataset, families)
        if delta.empty:
            theme.info_panel("The threshold PTPE could not be computed for the current selection.")
        else:
            theme.metric_cards(
                [
                    (
                        "Median \u0394T",
                        f"{delta['median_delta_t_db'].median():.2f} dB",
                        "Across families and frequencies.",
                    ),
                    (
                        "Median |\u0394T|",
                        f"{delta['median_delta_t_db'].abs().median():.2f} dB",
                        None,
                    ),
                    ("Families", str(delta["family"].nunique()), None),
                ]
            )
            figure = plotting.curves_figure(
                delta,
                x="frequency_hz",
                y="median_delta_t_db",
                series="family",
                title="Threshold PTPE \u0394T [dB]",
                y_title="\u0394T [dB]",
                y_reference=0.0,
            )
            figure.update_xaxes(type="linear", tickmode="array", tickvals=list(dataset.threshold_frequency_hz))
            figure.update_layout(height=440)
            st.plotly_chart(figure, width="stretch")
            heat = plotting.heatmap_figure(
                delta,
                index="family",
                columns="frequency_hz",
                value="median_delta_t_db",
                title="\u0394T heatmap (family \u00d7 frequency)",
                colorbar_title="\u0394T [dB]",
                height=380,
            )
            st.plotly_chart(heat, width="stretch")
            st.dataframe(delta, width="stretch", hide_index=True)
            ui.download_frame(delta, "threshold_ptpe_delta_t.csv", "Download \u0394T table (CSV)")

    with tabs[2]:
        theme.section_title(
            "Threshold vs coupling",
            "Subject-level median thresholds grouped by coupling. Earmold couplings are expected "
            "to be more sensitive at low frequencies than open/dome couplings.",
        )
        coupling_frame = _threshold_vs_coupling(dataset, conditions, families)
        if coupling_frame.empty:
            st.info("No coupling comparison is available for the current selection.")
        else:
            figure = go.Figure()
            for offset, (label, group) in enumerate(
                coupling_frame.groupby("coupling_label", sort=False)
            ):
                figure.add_trace(
                    go.Box(
                        x=group["threshold_frequency_hz"],
                        y=group["threshold_dbv"],
                        name=label,
                        marker_color=plotting.COLORWAY[offset % len(plotting.COLORWAY)],
                        boxpoints="all",
                        jitter=0.35,
                        pointpos=0,
                        hovertemplate="%{x:.4g} Hz<br>%{y:.2f} dBV<extra></extra>",
                    )
                )
            figure.update_xaxes(type="log", title_text="Frequency [Hz]")
            figure.update_yaxes(title_text="Threshold [dBV]", autorange="reversed")
            figure.update_layout(
                template=plotting.PLOTLY_TEMPLATE,
                title="Threshold distribution by coupling style",
                height=460,
                boxmode="group",
            )
            st.plotly_chart(figure, width="stretch")
            summary = (
                coupling_frame.groupby(["coupling_label", "threshold_frequency_hz"], as_index=False)[
                    "threshold_dbv"
                ]
                .median()
            )
            st.dataframe(summary, width="stretch", hide_index=True)
            ui.download_frame(summary, "threshold_by_coupling.csv", "Download coupling summary (CSV)")

    theme.section_title("Persisted E07 results")
    ui.result_summary_panel(result_for("E07"), code="E07", title="Hearing Threshold")
    theme.footnote(
        "Thresholds are stored as receiver voltage at threshold in dBV and are quantised to 1 dB "
        "by the measurement procedure; effect estimates smaller than 1 dB are therefore at the "
        "resolution limit of the data."
    )
