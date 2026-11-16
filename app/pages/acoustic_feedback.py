"""Page 3 — Acoustic Feedback.

The feedback path ``M_ha2haf`` (hearing-aid driver to hearing-aid microphone)
in dB SPL at the fixed 11.2 mV receiver drive: family/condition curves, band
levels and the reference-vs-measurement condition comparison.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from acousticbench.stats.bands import octave_bands
from acousticbench.types import Condition, P_REF_PA
from app.components import filters, plotting, theme, ui
from app.components.data import get_dataset_state, result_for

TITLE = "Acoustic Feedback"
SUBTITLE = (
    "Feedback path response between the hearing-aid receiver and its own microphone "
    "(M_ha2haf), by earpiece family and probe condition."
)


def _selection_frame(cube) -> pd.DataFrame:
    levels = cube.level_array()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        median = np.nanmedian(levels, axis=(2, 3))
    frequencies = np.asarray(cube.freq_hz, dtype=float)
    keep = frequencies >= 50.0
    frames = []
    for device_index, device in enumerate(cube.devices):
        frames.append(
            pd.DataFrame(
                {
                    "frequency_hz": frequencies[keep],
                    "device_code": device.code,
                    "family": device.family,
                    "family_label": device.family_label,
                    "condition": device.condition.label if device.condition else "\u2014",
                    "device": device.short_label,
                    "level_db": median[keep, device_index],
                }
            )
        )
    return pd.concat(frames, ignore_index=True).dropna(subset=["level_db"])


def _feedback_cube(dataset, conditions, families, subjects):
    cube, error = ui.safe_call(
        dataset.get,
        "M_ha2haf",
        conditions=conditions or None,
        families=families or None,
        subjects=subjects or None,
    )
    if error is not None or cube is None:
        return None, error
    return cube.magnitude_db(reference=P_REF_PA, unit_label="dB SPL @ 11.2 mV", name="Feedback path"), None


def render() -> None:
    """Render the Acoustic Feedback page."""
    theme.page_header(TITLE, SUBTITLE, eyebrow="Feedback path")
    dataset = ui.ensure_dataset()
    if dataset is None:
        return

    st.sidebar.markdown("### Feedback filters")
    conditions = filters.condition_widget("fb")
    families = filters.families_widget("fb")
    subjects = filters.subjects_widget("fb", dataset)

    cube, error = _feedback_cube(dataset, conditions, families, subjects)
    if error is not None or cube is None:
        theme.error_panel(f"The feedback path could not be computed: {error}")
        return
    frame = _selection_frame(cube)
    if frame.empty:
        st.info("No valid feedback-path values for the current selection.")

    theme.metric_cards(
        [
            ("Conditions", str(frame["condition"].nunique()), None),
            ("Families", str(frame["family"].nunique()), None),
            ("Subjects", str(int(cube.subjects.size)), None),
            ("Median level", f"{frame['level_db'].median():.1f} dB SPL", None),
        ]
    )

    tabs = st.tabs(["Curves", "Band levels", "Reference vs measurement"])
    with tabs[0]:
        theme.section_title(
            "Feedback path curves",
            "Median across the selected subjects; solid and dashed lines distinguish the probe "
            "conditions because the hearing-aid microphone is measured in both.",
        )
        figure = plotting.curves_figure(
            frame,
            x="frequency_hz",
            y="level_db",
            series="family",
            dash="condition",
            title="Feedback path Hfb [dB SPL @ 11.2 mV]",
            y_title="Hfb [dB SPL @ 11.2 mV]",
        )
        st.plotly_chart(figure, width="stretch")
        ui.download_frame(frame, "feedback_path_curves_filtered.csv", "Download curves (CSV)")
    with tabs[1]:
        theme.section_title(
            "Band levels",
            "Power-averaged feedback-path levels; select one condition to compare families.",
        )
        band_condition = st.selectbox(
            "Condition for band levels",
            options=[Condition.MEASUREMENT, Condition.REFERENCE],
            index=0,
            format_func=lambda value: value.label,
            key="fb_band_condition",
        )
        transfer_cube, transfer_error = ui.safe_call(
            dataset.get,
            "M_ha2haf",
            conditions=[band_condition],
            families=families or None,
            subjects=subjects or None,
        )
        bands = tuple(octave_bands())
        if transfer_error is not None or transfer_cube is None:
            theme.error_panel(f"Band levels unavailable: {transfer_error}")
        else:
            band_frame, band_error = ui.safe_call(
                transfer_cube.band_levels, bands, reference=P_REF_PA
            )
            if band_error is not None or band_frame is None:
                theme.error_panel(f"Band levels unavailable: {band_error}")
            else:
                valid = band_frame.loc[band_frame["valid"]]
                summary = (
                    valid.groupby(
                        ["family", "family_label", "band", "band_center_hz"], as_index=False
                    )["level_db"]
                    .median()
                    .sort_values(["band_center_hz", "family_label"])
                )
                figure = plotting.band_bar_figure(
                    summary,
                    band="band",
                    value="level_db",
                    series="family",
                    title=f"Feedback path band levels \u2014 {band_condition.label} condition",
                    x_title="Frequency band",
                    y_title="Hfb [dB SPL @ 11.2 mV]",
                    y_reference=None,
                )
                st.plotly_chart(figure, width="stretch")
                st.dataframe(summary, width="stretch", hide_index=True)
                ui.download_frame(summary, "feedback_band_levels_filtered.csv", "Download band levels (CSV)")
    with tabs[2]:
        theme.section_title(
            "Reference vs measurement condition",
            "Difference of the median feedback-path levels (measurement \u2212 reference). "
            "The same hearing-aid microphone is used in both conditions.",
        )
        merged = frame.copy()
        pivot = merged.pivot_table(
            index=["family", "family_label", "frequency_hz"],
            columns="condition",
            values="level_db",
        ).reset_index()
        if {"Measurement", "Reference"}.issubset(pivot.columns):
            pivot["delta_db"] = pivot["Measurement"] - pivot["Reference"]
            delta = pivot.dropna(subset=["delta_db"])
            figure = plotting.curves_figure(
                delta,
                x="frequency_hz",
                y="delta_db",
                series="family",
                title="Feedback path difference (measurement \u2212 reference)",
                y_title="Delta Hfb [dB]",
                y_reference=0.0,
            )
            st.plotly_chart(figure, width="stretch")
            st.dataframe(
                delta.groupby(["family_label"], as_index=False)["delta_db"]
                .agg(median_delta_db="median", n="count"),
                width="stretch",
                hide_index=True,
            )
            ui.download_frame(pivot, "feedback_condition_difference.csv", "Download comparison (CSV)")
        else:
            theme.info_panel("Select both probe conditions to compute the comparison overlay.")

    theme.section_title("Persisted E05 results")
    ui.result_summary_panel(result_for("E05"), code="E05", title="Acoustic Feedback")
    theme.footnote(
        "The feedback path is the ratio of hearing-aid microphone pressure to the fixed receiver "
        "drive voltage. It is a device-level quantity and exists for every family and condition."
    )
