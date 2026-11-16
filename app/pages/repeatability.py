"""Page 4 — Repeatability.

Within-subject reinsertion repeatability of Hha: frequency-resolved SD, band
summaries with ICC(2,1) and repeatability coefficients, per-family comparison,
and the persisted E03 result summary.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import streamlit as st

from acousticbench.measurements.transfer import hha_db_spl
from acousticbench.stats.bands import Band, octave_bands, third_octave_bands
from acousticbench.stats.icc import icc_2_1
from acousticbench.types import Condition, Probe
from app.components import filters, plotting, theme, ui
from app.components.data import get_config, result_for

TITLE = "Repeatability"
SUBTITLE = (
    "Within-subject reinsertion variability: the three reinsertions are technical repeats, "
    "so their spread quantifies measurement repeatability, not between-subject variability."
)

try:  # the measurements.repeatability module is part of the core contract
    from acousticbench.measurements import repeatability as _repeatability

    _HAS_REPEATABILITY = True
    _REPEATABILITY_ERROR = ""
except Exception as exc:  # noqa: BLE001 - optional integration guard
    _repeatability = None
    _HAS_REPEATABILITY = False
    _REPEATABILITY_ERROR = f"{type(exc).__name__}: {exc}"


def _fallback_sd_by_frequency(cube) -> pd.DataFrame:
    """Fallback per-frequency reinsertion SD (numpy, ddof=1, no imputation)."""
    levels = cube.level_array()
    with warnings.catch_warnings(), np.errstate(invalid="ignore"):
        warnings.simplefilter("ignore", category=RuntimeWarning)
        sd = np.nanstd(levels, axis=3, ddof=1)
        n_valid = np.isfinite(levels).sum(axis=3)
    sd = np.where(n_valid >= 2, sd, np.nan)
    frames = []
    n_freq, n_dev, n_subj, _ = levels.shape
    for device_index, device in enumerate(cube.devices):
        frames.append(
            pd.DataFrame(
                {
                    "frequency_hz": np.tile(cube.freq_hz, n_subj),
                    "device_code": device.code,
                    "family": device.family,
                    "family_label": device.family_label,
                    "subject": np.repeat(cube.subjects, n_freq),
                    "sd_db": sd[:, device_index, :].reshape(-1),
                }
            )
        )
    return pd.concat(frames, ignore_index=True).dropna(subset=["sd_db"])


def _fallback_band_summary(cube, bands: tuple[Band, ...]) -> pd.DataFrame:
    """Fallback band repeatability: arithmetic mean of dB within each band."""
    levels = cube.level_array()
    frequencies = np.asarray(cube.freq_hz, dtype=float)
    rows = []
    n_dev, n_subj, _ = levels.shape[1:]
    for band in bands:
        mask = band.contains(frequencies)
        if not mask.any():
            continue
        with warnings.catch_warnings(), np.errstate(invalid="ignore"):
            warnings.simplefilter("ignore", category=RuntimeWarning)
            band_levels = np.nanmean(levels[mask], axis=0)
            sd = np.nanstd(band_levels, axis=2, ddof=1)
        for device_index, device in enumerate(cube.devices):
            per_subject = band_levels[device_index]
            icc = float("nan")
            try:
                complete = np.isfinite(per_subject).all(axis=1)
                if complete.sum() >= 2:
                    icc = icc_2_1(per_subject[complete]).icc
            except Exception:  # noqa: BLE001 - ICC is optional in the fallback
                icc = float("nan")
            rows.append(
                {
                    "band": band.label,
                    "band_center_hz": band.center_hz,
                    "device_code": device.code,
                    "device": device.label,
                    "family": device.family,
                    "family_label": device.family_label,
                    "n_subjects": int(np.isfinite(per_subject).any(axis=1).sum()),
                    "median_level_db": float(np.nanmedian(per_subject)),
                    "sd_reinsertion_db_median": float(np.nanmedian(sd[device_index])),
                    "sd_reinsertion_db_p95": float(np.nanpercentile(sd[device_index], 95)),
                    "repeatability_coefficient_db": float(1.96 * np.sqrt(2.0) * np.nanmedian(sd[device_index])),
                    "icc_2_1": icc,
                }
            )
    return pd.DataFrame(rows)


def _family_band_value(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    aggregated = (
        frame.groupby(["family", "band", "band_center_hz"], as_index=False)[column]
        .median()
        .sort_values(["band_center_hz", "family"])
    )
    aggregated["family_label"] = aggregated["family"].map(plotting.family_label)
    return aggregated


def render() -> None:
    """Render the Repeatability page."""
    theme.page_header(TITLE, SUBTITLE, eyebrow="Reinsertion repeatability")
    dataset = ui.ensure_dataset()
    if dataset is None:
        return

    st.sidebar.markdown("### Repeatability filters")
    families = filters.families_widget("rp")
    subjects = filters.subjects_widget("rp", dataset)
    band_method = st.sidebar.radio(
        "Frequency bands",
        options=["octave", "third_octave"],
        index=0,
        format_func=lambda value: "Octave bands" if value == "octave" else "One-third-octave bands",
        key="rp_band_method",
    )
    bands = octave_bands() if band_method == "octave" else third_octave_bands()
    band_options = {
        "250 - 8000 Hz": (250.0, 8000.0),
        "500 - 4000 Hz": (500.0, 4000.0),
        "1000 - 8000 Hz": (1000.0, 8000.0),
    }
    band_label = st.sidebar.selectbox(
        "Summary band for per-family comparison",
        options=list(band_options),
        index=1,
        help="Wide band used for the per-device repeatability comparison.",
        key="rp_band_hz",
    )
    band_hz = band_options[band_label]

    cube, error = ui.safe_call(
        hha_db_spl,
        dataset,
        probe=Probe.MEASUREMENT,
        condition=Condition.MEASUREMENT,
        families=families or None,
        subjects=subjects or None,
    )
    if error is not None or cube is None:
        theme.error_panel(f"Repeatability inputs unavailable: {error}")
        return

    if not _HAS_REPEATABILITY:
        theme.warning_panel(
            "The <code>measurements.repeatability</code> module could not be imported "
            f"({_REPEATABILITY_ERROR}); the page falls back to an equivalent direct numpy "
            "computation. Per-frequency SDs use ddof=1 and no imputation; band levels use an "
            "arithmetic mean of dB values inside each band (documented approximation).",
            title="Fallback computation",
        )
        sd_frame = _fallback_sd_by_frequency(cube)
        band_frame = _fallback_band_summary(cube, tuple(bands))
        per_device_frame = _fallback_band_summary(cube, (Band("500\u20134000 Hz", 1414.2, band_hz[0], band_hz[1]),))
        source = "numpy fallback"
    else:
        sd_frame, sd_error = ui.safe_call(_repeatability.reinsertion_sd_by_frequency, cube)
        band_frame, band_error = ui.safe_call(_repeatability.repeatability_summary, cube, tuple(bands))
        per_device_frame, device_error = ui.safe_call(
            _repeatability.repeatability_by_device, cube, band_hz=band_hz
        )
        if any(value is not None for value in (sd_error, band_error, device_error)):
            theme.error_panel(
                f"Repeatability could not be computed: {sd_error or band_error or device_error}"
            )
            return
        source = "measurements.repeatability"

    if sd_frame is None or sd_frame.empty:
        st.info("No valid reinsertion pairs exist for the current selection.")
        return

    primary = sd_frame.loc[(sd_frame["frequency_hz"] >= 500.0) & (sd_frame["frequency_hz"] <= 4000.0)]
    median_sd = float(primary["sd_db"].median()) if not primary.empty else float("nan")
    median_icc = (
        float(band_frame["icc_2_1"].median())
        if band_frame is not None and not band_frame.empty
        else float("nan")
    )
    theme.metric_cards(
        [
            ("Within-subject SD (500\u20134000 Hz)", f"{median_sd:.2f} dB", "Median over frequencies, devices, subjects."),
            ("ICC(2,1)", f"{median_icc:.2f}" if np.isfinite(median_icc) else "\u2014", "Median over bands and devices."),
            ("Subjects", str(int(sd_frame["subject"].nunique())), None),
            ("Families", str(int(sd_frame["family"].nunique())), None),
            ("Computation", source, "Module used for this page's repeatability analysis."),
        ]
    )

    tabs = st.tabs(["Frequency-resolved SD", "Band summary", "Per-family comparison"])
    with tabs[0]:
        theme.section_title(
            "Frequency-resolved reinsertion SD",
            "Median across subjects of the within-subject sample SD (ddof=1) of the three "
            "reinsertions; only (device, subject, frequency) cells with at least two valid "
            "reinsertions contribute.",
        )
        curve = (
            sd_frame.loc[sd_frame["frequency_hz"] >= 50.0]
            .groupby(["family", "frequency_hz"], as_index=False)["sd_db"]
            .median()
        )
        curve["family_label"] = curve["family"].map(plotting.family_label)
        figure = plotting.curves_figure(
            curve,
            x="frequency_hz",
            y="sd_db",
            series="family",
            title="Within-subject reinsertion SD of Hha",
            y_title="SD [dB]",
            y_reference=None,
        )
        st.plotly_chart(figure, width="stretch")
        ui.download_frame(curve, "reinsertion_sd_by_frequency.csv", "Download frequency-resolved SD (CSV)")
    with tabs[1]:
        theme.section_title(
            "Band-level repeatability",
            "Per family and band: median within-subject SD, its 95th percentile, the "
            "repeatability coefficient 1.96\u00b7\u221a2\u00b7SD and ICC(2,1).",
        )
        if band_frame is None or band_frame.empty:
            st.info("No band repeatability could be computed for the current selection.")
        else:
            sd_heat = _family_band_value(band_frame, "sd_reinsertion_db_median")
            figure = plotting.heatmap_figure(
                sd_heat,
                index="family",
                columns="band",
                value="sd_reinsertion_db_median",
                title="Median within-subject SD per band [dB]",
                colorbar_title="SD [dB]",
                colorscale="YlOrRd",
                zmid=None,
                height=420,
            )
            st.plotly_chart(figure, width="stretch")
            display_columns = [
                column
                for column in (
                    "family",
                    "band",
                    "band_center_hz",
                    "n_subjects",
                    "median_level_db",
                    "sd_reinsertion_db_median",
                    "sd_reinsertion_db_p95",
                    "repeatability_coefficient_db",
                    "icc_2_1",
                )
                if column in band_frame.columns
            ]
            st.dataframe(band_frame[display_columns], width="stretch", hide_index=True, height=360)
            ui.download_frame(band_frame, "repeatability_band_summary.csv", "Download band summary (CSV)")
    with tabs[2]:
        theme.section_title(
            f"Per-family comparison \u2014 {band_hz[0]:g}\u2013{band_hz[1]:g} Hz",
            "One wide band per family: ICC(2,1) and the median within-subject SD.",
        )
        if per_device_frame is None or per_device_frame.empty:
            st.info("No per-device repeatability could be computed for the current selection.")
        else:
            summary = (
                per_device_frame.groupby(["family"], as_index=False)
                .agg(
                    sd_reinsertion_db_median=("sd_reinsertion_db_median", "median"),
                    icc_2_1=("icc_2_1", "median"),
                    n_subjects=("n_subjects", "max"),
                )
                .sort_values("sd_reinsertion_db_median")
            )
            summary["family_label"] = summary["family"].map(plotting.family_label)
            import plotly.graph_objects as go

            figure = go.Figure()
            figure.add_trace(
                go.Bar(
                    x=summary["family_label"],
                    y=summary["sd_reinsertion_db_median"],
                    name="Median within-subject SD [dB]",
                    marker_color=[plotting.family_colour(family) for family in summary["family"]],
                    hovertemplate="%{x}<br>SD %{y:.2f} dB<extra></extra>",
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=summary["family_label"],
                    y=summary["icc_2_1"],
                    name="ICC(2,1)",
                    mode="markers+lines",
                    yaxis="y2",
                    marker=dict(size=9, color="#22303c"),
                    hovertemplate="%{x}<br>ICC %{y:.2f}<extra></extra>",
                )
            )
            figure.update_layout(
                template=plotting.PLOTLY_TEMPLATE,
                title=f"Repeatability per family, {band_hz[0]:g}\u2013{band_hz[1]:g} Hz",
                yaxis=dict(title="Within-subject SD [dB]"),
                yaxis2=dict(title="ICC(2,1)", overlaying="y", side="right", range=[0, 1]),
                height=430,
                legend=dict(orientation="h", y=1.02, x=0),
            )
            st.plotly_chart(figure, width="stretch")
            st.dataframe(summary, width="stretch", hide_index=True)
            ui.download_frame(summary, "repeatability_per_family.csv", "Download per-family summary (CSV)")

    theme.section_title("Persisted E03 results")
    ui.result_summary_panel(result_for("E03"), code="E03", title="Measurement Repeatability")
    config = get_config()
    theme.footnote(
        f"Within-subject reinsertion SD uses the sample standard deviation (ddof=1); "
        f"undefined cells (fewer than two valid reinsertions) remain NaN. "
        f"Configured ICC method: {config.get('experiments.params.E03.icc_method', 'icc2')}."
    )
