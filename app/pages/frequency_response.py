"""Page 2 — Frequency Response (Hha).

Hha curves in dB SPL at the fixed 11.2 mV receiver drive, with probe,
condition, family, device and subject filters; median versus individual
subjects; octave/third-octave band levels; band-level heatmap; comparison
overlay; and the persisted E01 result summary.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from acousticbench.exceptions import MeasurementError
from acousticbench.measurements.transfer import hha_band_levels, hha_db_spl
from acousticbench.stats.bands import octave_bands
from acousticbench.types import DEVICES, Condition, Probe
from app.components import filters, plotting, theme, ui
from app.components.data import result_for

TITLE = "Frequency Response"
SUBTITLE = (
    "Hha \u2014 hearing-aid driver response at the eardrum in dB SPL at the 11.2 mV "
    "receiver drive, with median/individual curves and band-level summaries."
)


def _median_frame(cube) -> pd.DataFrame:
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
                    "device": device.short_label,
                    "median_db": median[keep, device_index],
                }
            )
        )
    return pd.concat(frames, ignore_index=True).dropna(subset=["median_db"])


def _individual_frame(cube) -> pd.DataFrame:
    subject_means = cube.subject_level_means()
    frequencies = np.asarray(cube.freq_hz, dtype=float)
    keep = frequencies >= 50.0
    frames = []
    for device_index, device in enumerate(cube.devices):
        for subject_index, subject in enumerate(cube.subjects):
            values = subject_means[keep, device_index, subject_index]
            frames.append(
                pd.DataFrame(
                    {
                        "frequency_hz": frequencies[keep],
                        "family": device.family,
                        "device": device.short_label,
                        "subject": int(subject),
                        "level_db": values,
                    }
                )
            )
    return pd.concat(frames, ignore_index=True).dropna(subset=["level_db"])


def _curves_tab(dataset, probe, condition, families, devices, subjects, show_individual: bool) -> None:
    theme.section_title(
        "Hha curves",
        "Median across the selected subjects and reinsertions (bold) and, optionally, the "
        "subject-level reinsertion means (thin lines).",
    )
    cube, error = ui.safe_call(
        hha_db_spl,
        dataset,
        probe=probe,
        condition=condition,
        families=families or None,
        device_codes=devices or None,
        subjects=subjects or None,
    )
    if error is not None or cube is None:
        theme.error_panel(
            f"{error}<br/>The reference condition requires the <strong>reference probe</strong> "
            "and exists for earmolds only; choose a compatible probe/condition pair or exclude "
            "dome families for reference-probe views.",
            title="Hha cannot be computed for this probe/condition selection",
        )
        return
    median_frame = _median_frame(cube)
    if median_frame.empty:
        st.info("No valid Hha values exist for the current selection.")
        return
    figure = plotting.curves_figure(
        median_frame,
        x="frequency_hz",
        y="median_db",
        series="family",
        title=f"Hha median curves \u2014 {Probe(probe).label}, {Condition(condition).label} condition",
        y_title="Hha [dB SPL @ 11.2 mV]",
    )
    if show_individual:
        individual = _individual_frame(cube)
        for offset, (family, group) in enumerate(individual.groupby("family", sort=False)):
            exact_colour = plotting.family_colour(str(family), offset)
            for _, subject_group in group.groupby("subject", sort=False):
                figure.add_trace(
                    go.Scatter(
                        x=subject_group["frequency_hz"],
                        y=subject_group["level_db"],
                        mode="lines",
                        line=dict(color=exact_colour, width=0.6),
                        opacity=0.28,
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
    st.plotly_chart(figure, width="stretch")
    ui.download_frame(median_frame, "hha_median_curves_filtered.csv", "Download median curves (CSV)")

    with st.expander("Band levels (table)", expanded=False):
        bands = tuple(st.session_state.get("fr_bands") or octave_bands())
        if bands:
            band_frame, band_error = ui.safe_call(
                hha_band_levels,
                dataset,
                bands,
                probe=probe,
                condition=condition,
                families=families or None,
                device_codes=devices or None,
                subjects=subjects or None,
            )
            if band_error is None and band_frame is not None:
                table = (
                    band_frame.loc[band_frame["valid"]]
                    .groupby(["family_label", "band", "band_center_hz"], as_index=False)[
                        "level_db"
                    ]
                    .median()
                    .sort_values(["band_center_hz", "family_label"])
                )
                st.dataframe(table, width="stretch", hide_index=True)
                ui.download_frame(table, "hha_band_levels_filtered.csv", "Download band levels (CSV)")


def _band_tab(dataset, probe, condition, families, devices, subjects) -> None:
    theme.section_title(
        "Frequency-band levels",
        "Power-averaged Hha per band (the physically correct aggregation over DFT bins).",
    )
    bands = filters.band_set_widget("fr")
    st.session_state["fr_bands"] = bands
    band_frame, error = ui.safe_call(
        hha_band_levels,
        dataset,
        bands,
        probe=probe,
        condition=condition,
        families=families or None,
        device_codes=devices or None,
        subjects=subjects or None,
    )
    if error is not None or band_frame is None:
        theme.error_panel(f"Hha band levels unavailable: {error}")
        return
    valid = band_frame.loc[band_frame["valid"]]
    if valid.empty:
        st.info("No valid band levels for the current selection.")
        return
    summary = (
        valid.groupby(["family", "family_label", "band", "band_center_hz"], as_index=False)["level_db"]
        .median()
        .sort_values(["band_center_hz", "family_label"])
    )
    theme.metric_cards(
        [
            ("Bands", str(summary["band"].nunique()), None),
            ("Families", str(summary["family"].nunique()), None),
            ("Median level", f"{summary['level_db'].median():.1f} dB SPL", None),
            ("Subjects", str(int(valid["subject"].nunique())), None),
        ]
    )
    figure = plotting.band_bar_figure(
        summary,
        band="band",
        value="level_db",
        series="family",
        title="Band-level Hha per family",
        x_title="Frequency band",
        y_title="Hha [dB SPL @ 11.2 mV]",
        y_reference=None,
    )
    st.plotly_chart(figure, width="stretch")

    st.markdown("**Band-level heatmap (median across subjects)**")
    heatmap = summary.assign(family=summary["family_label"])
    heat = plotting.heatmap_figure(
        heatmap,
        index="family",
        columns="band",
        value="level_db",
        title="Hha band levels [dB SPL]",
        colorbar_title="dB SPL",
        colorscale="YlGnBu",
        zmid=None,
        height=380,
    )
    st.plotly_chart(heat, width="stretch")
    st.dataframe(summary, width="stretch", hide_index=True)
    ui.download_frame(summary, "hha_band_levels_summary_filtered.csv", "Download band summary (CSV)")


def _comparison_tab(dataset, condition, families, subjects) -> None:
    theme.section_title(
        "Comparison overlay",
        "Reference probe in both probe conditions: isolates the acoustic probe-tube presence "
        "effect (earmolds only, because no reference probe exists for domes).",
    )
    theme.warning_panel(
        "This comparison uses the reference probe tube, available for earmolds only. "
        "Dome families are excluded by design, not by data quality.",
        title="Earmold-only comparison",
    )
    earmold_families = [
        family
        for family in (families or [])
        if family in {"closed_earmold", "vented_earmold", "nugget_earmold", "silicone_earmold"}
    ] or ["closed_earmold", "vented_earmold", "nugget_earmold", "silicone_earmold"]
    frames = []
    for condition_value, label in (
        (Condition.MEASUREMENT, "Measurement condition"),
        (Condition.REFERENCE, "Reference condition"),
    ):
        cube, error = ui.safe_call(
            hha_db_spl,
            dataset,
            probe=Probe.REFERENCE,
            condition=condition_value,
            families=earmold_families,
            subjects=subjects or None,
        )
        if error is not None or cube is None:
            theme.error_panel(f"Cannot compute the {label}: {error}")
            return
        frame = _median_frame(cube)
        frame["condition"] = label
        frames.append(frame)
    merged = pd.concat(frames, ignore_index=True)
    figure = plotting.curves_figure(
        merged,
        x="frequency_hz",
        y="median_db",
        series="family",
        dash="condition",
        title="Hha \u2014 reference vs measurement probe condition (reference probe)",
        y_title="Hha [dB SPL @ 11.2 mV]",
    )
    st.plotly_chart(figure, width="stretch")
    pivot = merged.pivot_table(
        index=["family_label", "frequency_hz"],
        columns="condition",
        values="median_db",
    ).reset_index()
    pivot.columns.name = None
    if {"Measurement condition", "Reference condition"}.issubset(pivot.columns):
        pivot["Delta (measurement - reference) [dB]"] = (
            pivot["Measurement condition"] - pivot["Reference condition"]
        )
        with st.expander("Reference-vs-measurement difference (table)", expanded=False):
            st.dataframe(pivot, width="stretch", hide_index=True, height=320)
            ui.download_frame(pivot, "hha_condition_comparison.csv", "Download comparison (CSV)")


def render() -> None:
    """Render the Frequency Response page."""
    theme.page_header(TITLE, SUBTITLE, eyebrow="Hearing-aid driver response")
    dataset = ui.ensure_dataset()
    if dataset is None:
        return

    st.sidebar.markdown("### Hha filters")
    probe = filters.probe_widget("fr", default=Probe.MEASUREMENT) or Probe.MEASUREMENT
    condition = st.sidebar.radio(
        "Probe condition",
        options=[Condition.MEASUREMENT, Condition.REFERENCE],
        index=0,
        format_func=lambda value: value.label,
        key="fr_condition",
        help="The reference condition is only meaningful with the reference probe (earmolds).",
    )
    families = filters.families_widget("fr")
    subjects = filters.subjects_widget("fr", dataset)
    device_options = [
        device
        for device in DEVICES
        if device.family in set(families) and device.condition is condition
    ]
    devices = filters.device_widget("fr", device_options)
    show_individual = st.sidebar.checkbox(
        "Show individual subjects",
        value=False,
        help="Thin lines: subject-level mean over the three reinsertions.",
        key="fr_show_individual",
    )

    result = result_for("E01")
    metric_items = [
        ("Probe", Probe(probe).label, None),
        ("Condition", Condition(condition).label, None),
        (
            "Families selected",
            str(len(families) if families else len({device.family for device in DEVICES})),
            None,
        ),
        ("Subjects selected", str(len(subjects)), None),
        (
            "E01 status",
            result.status if result is not None else "not available",
            "Persisted experiment E01 \u2014 Frequency Response.",
        ),
    ]
    theme.metric_cards(metric_items)

    tabs = st.tabs(["Hha curves", "Band levels", "Comparison overlay"])
    with tabs[0]:
        _curves_tab(dataset, probe, condition, families, devices, subjects, show_individual)
    with tabs[1]:
        _band_tab(dataset, probe, condition, families, devices, subjects)
    with tabs[2]:
        _comparison_tab(dataset, condition, families, subjects)

    theme.section_title("Persisted E01 results")
    ui.result_summary_panel(result, code="E01", title="Frequency Response")
    theme.footnote(
        "Hha is the eardrum pressure per fixed 11.2 mV receiver drive, expressed in dB SPL. "
        "It is a transfer-function magnitude, not an in-situ speech level."
    )
