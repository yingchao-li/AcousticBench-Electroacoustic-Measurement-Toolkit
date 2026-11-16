"""Page 6 — Statistical Analysis.

Subject-level paired comparisons with configurable bootstrap resampling,
confidence level, test, and multiple-comparison correction:

* ΔHha at 100 Hz versus zero, per earmold family (probe-tube presence effect);
* closed earmold versus open dome Hha at 1 kHz (same subjects, paired design).

Effect sizes, raw p values, corrected p values and bootstrap confidence
intervals are reported together; the subject is the independent statistical
unit (reinsertions are averaged within subject first).
"""

from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from acousticbench.measurements.ptpe import ptpe_hha_db
from acousticbench.measurements.transfer import hha_db_spl
from acousticbench.types import Condition, Probe
from app.components import plotting, theme, ui
from app.components.data import get_config

TITLE = "Statistical Analysis"
SUBTITLE = (
    "Subject-level paired comparisons of the acoustic measurements with bootstrap confidence "
    "intervals, effect sizes and multiple-comparison correction."
)

# ---------------------------------------------------------------------------
# Statistics backend: prefer acousticbench.stats, fall back to scipy
# ---------------------------------------------------------------------------
try:
    from acousticbench.stats.bootstrap import bootstrap_ci, bootstrap_paired_ci
    from acousticbench.stats.correction import benjamini_hochberg, holm_bonferroni
    from acousticbench.stats.effect_size import cohen_dz, rank_biserial
    from acousticbench.stats.paired import paired_t_test, wilcoxon_signed_rank

    _BACKEND = "acousticbench.stats"
    _BACKEND_ERROR = ""
    _HAS_STATS = True
except Exception as exc:  # noqa: BLE001 - optional integration guard
    _BACKEND = "scipy fallback"
    _BACKEND_ERROR = f"{type(exc).__name__}: {exc}"
    _HAS_STATS = False


def _fallback_paired_t(a: np.ndarray, b: np.ndarray, confidence: float) -> dict[str, Any]:
    """Minimal paired t-test fallback (scipy) used only if stats is unavailable."""
    from scipy import stats

    differences = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    n = differences.size
    mean_diff = float(np.mean(differences))
    sd_diff = float(np.std(differences, ddof=1))
    standard_error = sd_diff / math.sqrt(n)
    result = stats.ttest_rel(a, b)
    quantile = float(stats.t.ppf(1.0 - (1.0 - confidence) / 2.0, n - 1))
    return {
        "method": "paired_t_test (scipy fallback)",
        "n": n,
        "mean_diff": mean_diff,
        "ci_low": mean_diff - quantile * standard_error,
        "ci_high": mean_diff + quantile * standard_error,
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "effect_size": mean_diff / sd_diff if sd_diff > 0 else float("nan"),
        "effect_size_name": "cohen_dz",
    }


def _fallback_wilcoxon(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    """Minimal Wilcoxon signed-rank fallback (scipy) used only if stats is unavailable."""
    from scipy import stats

    differences = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    result = stats.wilcoxon(a, b, zero_method="wilcox", correction=False)
    ranks = stats.rankdata(np.abs(differences[differences != 0]))
    positive = float(np.sum(ranks[differences[differences != 0] > 0]))
    total = float(np.sum(ranks))
    rank_biserial_value = (positive - (total - positive)) / total if total > 0 else float("nan")
    return {
        "method": "wilcoxon_signed_rank (scipy fallback)",
        "n": int(differences.size),
        "mean_diff": float(np.mean(differences)),
        "median_diff": float(np.median(differences)),
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "effect_size": rank_biserial_value,
        "effect_size_name": "rank_biserial",
    }


def _fallback_bootstrap_ci(
    values: np.ndarray,
    *,
    n_resamples: int,
    confidence: float,
    seed: int,
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean (numpy fallback)."""
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    draws = np.empty(int(n_resamples), dtype=float)
    for index in range(int(n_resamples)):
        draws[index] = float(np.mean(rng.choice(values, size=values.size, replace=True)))
    alpha = 1.0 - confidence
    low, high = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(low), float(high)


def _fallback_correction(p_values: list[float], method: str) -> np.ndarray:
    """Holm/BH adjusted p-values fallback (numpy)."""
    values = np.asarray(p_values, dtype=float)
    if method == "none":
        return values.copy()
    order = np.argsort(values)
    sorted_values = values[order]
    n = sorted_values.size
    adjusted = np.empty(n, dtype=float)
    if method == "holm":
        cumulative = 0.0
        for index, value in enumerate(sorted_values):
            cumulative = max(cumulative, (n - index) * value)
            adjusted[index] = min(1.0, cumulative)
    else:  # benjamini-hochberg
        cumulative = 1.0
        for index in range(n - 1, -1, -1):
            cumulative = min(cumulative, n * sorted_values[index] / (index + 1))
            adjusted[index] = min(1.0, cumulative)
    result = np.empty(n, dtype=float)
    result[order] = adjusted
    return result


# ---------------------------------------------------------------------------
# Comparison assembly
# ---------------------------------------------------------------------------
def _subject_levels_at_frequency(cube, frequency_hz: float) -> dict[str, np.ndarray]:
    """Return subject-level (reinsertion-mean) levels per family at one frequency."""
    frequencies = np.asarray(cube.freq_hz, dtype=float)
    index = int(np.argmin(np.abs(frequencies - float(frequency_hz))))
    levels = cube.level_array()[:, :, :, :]
    subject_mean = np.nanmean(levels[index], axis=2)  # (device, subject)
    return {device.family: subject_mean[device_index] for device_index, device in enumerate(cube.devices)}


def _one_sample_test(
    values: np.ndarray,
    *,
    method: str,
    confidence: float,
    n_resamples: int,
    seed: int,
) -> dict[str, Any]:
    finite = np.isfinite(values)
    data = np.asarray(values[finite], dtype=float)
    zeros = np.zeros_like(data)
    if data.size < 3:
        return {"error": f"only {data.size} complete subject(s); at least 3 are required"}
    if _HAS_STATS:
        if method == "t":
            result = paired_t_test(data, zeros, confidence=confidence)
            row = {
                "method": result.method,
                "statistic": result.t,
                "p_value": result.p_value,
                "effect_size": result.effect_size,
                "effect_size_name": result.effect_size_name,
            }
        else:
            result = wilcoxon_signed_rank(data, zeros)
            row = {
                "method": result["method"],
                "statistic": result["statistic"],
                "p_value": result["p_value"],
                "effect_size": result["effect_size"],
                "effect_size_name": result["effect_size_name"],
            }
        bootstrap = bootstrap_ci(
            data,
            statistic=np.mean,
            n_resamples=int(n_resamples),
            confidence=confidence,
            seed=int(seed),
            method="percentile",
        )
        row.update(
            {
                "n": int(data.size),
                "estimate": float(np.mean(data)) if method == "t" else float(np.median(data)),
                "estimate_mean": float(np.mean(data)),
                "ci_low": bootstrap.ci_low,
                "ci_high": bootstrap.ci_high,
            }
        )
        return row
    fallback = (
        _fallback_paired_t(data, zeros, confidence)
        if method == "t"
        else _fallback_wilcoxon(data, zeros)
    )
    ci_low, ci_high = _fallback_bootstrap_ci(
        data, n_resamples=n_resamples, confidence=confidence, seed=seed
    )
    fallback.update(
        {
            "n": int(data.size),
            "estimate": fallback["mean_diff"] if method == "t" else fallback["median_diff"],
            "estimate_mean": float(np.mean(data)),
            "ci_low": ci_low,
            "ci_high": ci_high,
        }
    )
    return fallback


def _paired_test(
    a: np.ndarray,
    b: np.ndarray,
    *,
    method: str,
    confidence: float,
    n_resamples: int,
    seed: int,
) -> dict[str, Any]:
    finite = np.isfinite(a) & np.isfinite(b)
    first, second = np.asarray(a[finite], dtype=float), np.asarray(b[finite], dtype=float)
    if first.size < 3:
        return {"error": f"only {first.size} complete subject pair(s); at least 3 are required"}
    differences = first - second
    if _HAS_STATS:
        if method == "t":
            result = paired_t_test(first, second, confidence=confidence)
            row = {
                "method": result.method,
                "statistic": result.t,
                "p_value": result.p_value,
                "effect_size": result.effect_size,
                "effect_size_name": result.effect_size_name,
            }
        else:
            result = wilcoxon_signed_rank(first, second)
            row = {
                "method": result["method"],
                "statistic": result["statistic"],
                "p_value": result["p_value"],
                "effect_size": result["effect_size"],
                "effect_size_name": result["effect_size_name"],
            }
        bootstrap = bootstrap_paired_ci(
            first,
            second,
            statistic=np.mean,
            n_resamples=int(n_resamples),
            confidence=confidence,
            seed=int(seed),
            method="percentile",
        )
        row.update(
            {
                "n": int(first.size),
                "estimate": float(np.mean(differences)) if method == "t" else float(np.median(differences)),
                "estimate_mean": float(np.mean(differences)),
                "ci_low": bootstrap.ci_low,
                "ci_high": bootstrap.ci_high,
            }
        )
        return row
    fallback = (
        _fallback_paired_t(first, second, confidence)
        if method == "t"
        else _fallback_wilcoxon(first, second)
    )
    ci_low, ci_high = _fallback_bootstrap_ci(
        differences, n_resamples=n_resamples, confidence=confidence, seed=seed
    )
    fallback.update(
        {
            "n": int(first.size),
            "estimate": fallback["mean_diff"] if method == "t" else fallback["median_diff"],
            "estimate_mean": float(np.mean(differences)),
            "ci_low": ci_low,
            "ci_high": ci_high,
        }
    )
    return fallback


def _correct(p_values: list[float], method: str) -> np.ndarray:
    if method == "none":
        return np.asarray(p_values, dtype=float)
    if _HAS_STATS:
        if method == "holm":
            return holm_bonferroni(p_values)
        return benjamini_hochberg(p_values)
    return _fallback_correction(p_values, method)


def render() -> None:
    """Render the Statistical Analysis page."""
    theme.page_header(TITLE, SUBTITLE, eyebrow="Inference")
    dataset = ui.ensure_dataset()
    if dataset is None:
        return
    config = get_config()

    st.sidebar.markdown("### Inference settings")
    default_resamples = int(config.analysis.bootstrap.n_resamples)
    resample_options = sorted({1000, 2000, 5000, 10000, 20000, default_resamples})
    n_resamples = st.sidebar.selectbox(
        "Bootstrap resamples",
        options=resample_options,
        index=resample_options.index(default_resamples),
        key="sa_resamples",
        help="Percentile bootstrap over subjects (the independent unit).",
    )
    seed = st.sidebar.number_input(
        "Bootstrap seed",
        min_value=0,
        max_value=2**31 - 1,
        value=int(config.analysis.bootstrap.seed),
        step=1,
        key="sa_seed",
    )
    confidence = st.sidebar.selectbox(
        "Confidence level",
        options=[0.90, 0.95, 0.99],
        index=1,
        format_func=lambda value: f"{value:.0%}",
        key="sa_confidence",
    )
    test_method = st.sidebar.radio(
        "Test",
        options=["t", "wilcoxon"],
        index=0,
        format_func=lambda value: "Paired t-test" if value == "t" else "Wilcoxon signed-rank",
        key="sa_test",
    )
    correction_method = st.sidebar.selectbox(
        "Multiple-comparison correction",
        options=["holm", "benjamini-hochberg", "none"],
        index=0,
        key="sa_correction",
    )
    alpha = st.sidebar.number_input(
        "Significance level (alpha)",
        min_value=0.001,
        max_value=0.2,
        value=float(config.analysis.alpha),
        step=0.005,
        format="%.3f",
        key="sa_alpha",
    )
    earmold_families = ["closed_earmold", "vented_earmold", "nugget_earmold", "silicone_earmold"]
    selected_families = st.sidebar.multiselect(
        "Delta-Hha families",
        options=earmold_families,
        default=earmold_families,
        format_func=lambda family: plotting.family_label(family),
        key="sa_families",
        help="The probe-tube presence effect on Hha is defined for earmold couplings only.",
    )

    if not _HAS_STATS:
        theme.warning_panel(
            "The <code>acousticbench.stats</code> module could not be imported "
            f"({_BACKEND_ERROR}); this page uses an explicitly labelled scipy fallback "
            "implementing the same paired t-test / Wilcoxon / percentile-bootstrap / Holm logic.",
            title="Statistics backend fallback",
        )

    # ------------------------------------------------------------------
    # Comparison 1: Delta Hha at 100 Hz versus zero, per earmold family
    # ------------------------------------------------------------------
    rows: list[dict[str, Any]] = []
    raw_tables: dict[str, pd.DataFrame] = {}

    hha_delta_cube, delta_error = ui.safe_call(ptpe_hha_db, dataset)
    if delta_error is None and hha_delta_cube is not None:
        subject_levels = _subject_levels_at_frequency(hha_delta_cube, 100.0)
        for family in selected_families:
            values = subject_levels.get(family)
            if values is None:
                continue
            result = _one_sample_test(
                values,
                method=test_method,
                confidence=confidence,
                n_resamples=n_resamples,
                seed=seed,
            )
            row = {
                "Comparison": "Delta Hha at 100 Hz vs 0",
                "Group": plotting.family_label(family),
                "Family": family,
                **result,
            }
            rows.append(row)
            raw_tables[f"delta_hha_100Hz_{family}"] = pd.DataFrame(
                {
                    "subject": [int(value) for value in dataset.subjects],
                    "delta_hha_100Hz_db": values,
                }
            )
    else:
        theme.warning_panel(
            f"The Delta-Hha comparison could not be computed: {delta_error}",
            title="Comparison unavailable",
        )

    # ------------------------------------------------------------------
    # Comparison 2: closed earmold versus open dome Hha at 1 kHz
    # ------------------------------------------------------------------
    hha_cube, hha_error = ui.safe_call(
        hha_db_spl,
        dataset,
        probe=Probe.MEASUREMENT,
        condition=Condition.MEASUREMENT,
    )
    if hha_error is None and hha_cube is not None:
        subject_levels = _subject_levels_at_frequency(hha_cube, 1000.0)
        closed = subject_levels.get("closed_earmold")
        open_dome = subject_levels.get("open_dome")
        if closed is not None and open_dome is not None:
            result = _paired_test(
                closed,
                open_dome,
                method=test_method,
                confidence=confidence,
                n_resamples=n_resamples,
                seed=seed,
            )
            rows.append(
                {
                    "Comparison": "Closed earmold vs open dome Hha at 1 kHz",
                    "Group": "Closed Earmold \u2212 Open Dome",
                    "Family": "closed_vs_open",
                    **result,
                }
            )
            raw_tables["closed_vs_open_hha_1kHz"] = pd.DataFrame(
                {
                    "subject": [int(value) for value in dataset.subjects],
                    "closed_earmold_hha_1kHz_db": closed,
                    "open_dome_hha_1kHz_db": open_dome,
                    "difference_db": closed - open_dome,
                }
            )
    else:
        theme.warning_panel(
            f"The closed-vs-open comparison could not be computed: {hha_error}",
            title="Comparison unavailable",
        )

    valid_rows = [row for row in rows if "error" not in row]

    configured = {
        "n_resamples": int(n_resamples),
        "seed": int(seed),
        "confidence": float(confidence),
        "test": "paired_t_test" if test_method == "t" else "wilcoxon_signed_rank",
        "correction": correction_method,
        "alpha": float(alpha),
        "backend": _BACKEND,
    }

    # Correction requires all p values together.
    if valid_rows:
        p_values = [float(row["p_value"]) for row in valid_rows]
        adjusted = _correct(p_values, correction_method)
        for row, adjusted_value in zip(valid_rows, adjusted):
            row["p_adjusted"] = float(adjusted_value)
    for row in rows:
        if "error" in row:
            st.warning(f"{row['Comparison']} ({row['Group']}): {row['error']}")

    theme.metric_cards(
        [
            ("Comparisons computed", str(len(valid_rows)), None),
            ("Bootstrap resamples", f"{int(n_resamples):,}", f"Seed {int(seed)}."),
            ("Correction", correction_method, f"Alpha {alpha:g}."),
            (
                "Significant (corrected)",
                str(sum(1 for row in valid_rows if row.get("p_adjusted", 1.0) < alpha)),
                "Comparisons below the significance level after correction.",
            ),
            ("Backend", _BACKEND, "Statistics implementation used for this analysis."),
        ]
    )

    if not valid_rows:
        theme.warning_panel(
            "No comparison could be computed with the current data and settings.",
            title="Nothing to report",
        )
    else:
        table = pd.DataFrame(
            [
                {
                    "Comparison": row["Comparison"],
                    "Group": row["Group"],
                    "n": row.get("n", "\u2014"),
                    "Estimate [dB]": row.get("estimate"),
                    "CI low [dB]": row.get("ci_low"),
                    "CI high [dB]": row.get("ci_high"),
                    "Test": row.get("method", "\u2014"),
                    "Statistic": row.get("statistic"),
                    "p (raw)": row.get("p_value"),
                    "p (corrected)": row.get("p_adjusted"),
                    "Effect size": row.get("effect_size"),
                    "Effect name": row.get("effect_size_name", "\u2014"),
                }
                for row in valid_rows
            ]
        )
        forest = pd.DataFrame(
            [
                {
                    "label": f"{row['Comparison']}\n{row['Group']}",
                    "estimate": row.get("estimate"),
                    "ci_low": row.get("ci_low"),
                    "ci_high": row.get("ci_high"),
                    "kind": row["Comparison"],
                }
                for row in valid_rows
            ]
        )
        theme.section_title(
            "Comparison results",
            "Estimate = mean difference for the t-test, median difference for Wilcoxon; the "
            "confidence interval always comes from the subject-level percentile bootstrap.",
        )
        st.dataframe(
            table.style.format(
                {
                    "Estimate [dB]": "{:.2f}",
                    "CI low [dB]": "{:.2f}",
                    "CI high [dB]": "{:.2f}",
                    "p (raw)": "{:.4g}",
                    "p (corrected)": "{:.4g}",
                    "Effect size": "{:.2f}",
                },
                na_rep="\u2014",
            ),
            width="stretch",
            hide_index=True,
            height=min(420, 60 + 36 * len(table)),
        )
        ui.download_frame(table, "statistical_comparisons.csv", "Download comparison table (CSV)")

        theme.section_title(
            "Effect-size forest plot",
            "Point estimate with the bootstrap confidence interval; the vertical line marks zero.",
        )
        figure = go.Figure()
        for kind, group in forest.groupby("kind", sort=False):
            figure.add_trace(
                go.Scatter(
                    x=group["estimate"],
                    y=group["label"],
                    mode="markers",
                    name=str(kind),
                    marker=dict(size=9, color=plotting.COLORWAY[0] if "Delta" not in str(kind) else plotting.COLORWAY[1]),
                    error_x=dict(
                        type="data",
                        symmetric=False,
                        array=group["ci_high"] - group["estimate"],
                        arrayminus=group["estimate"] - group["ci_low"],
                        color="#33434f",
                        thickness=1.4,
                        width=5,
                    ),
                    hovertemplate="%{y}<br>%{x:.2f} dB<extra></extra>",
                )
            )
        figure.add_vline(x=0.0, line_dash="dash", line_color="#5b6770")
        figure.update_layout(
            template=plotting.PLOTLY_TEMPLATE,
            title="Subject-level effect estimates with bootstrap CI",
            xaxis_title="Difference [dB]",
            height=420,
            showlegend=True,
        )
        st.plotly_chart(figure, width="stretch")

        with st.expander("Subject-level data used in the comparisons", expanded=False):
            for name, frame in raw_tables.items():
                st.markdown(f"`{name}`")
                st.dataframe(frame, width="stretch", hide_index=True)
                ui.download_frame(frame, f"{name}.csv", f"Download {name} (CSV)")

    with st.expander("Analysis settings used", expanded=False):
        st.json(configured)

    theme.footnote(
        "Subject is the independent statistical unit: the three reinsertions are averaged within "
        "subject before any inference. Wilcoxon p values are exact/asymptotic as implemented by "
        "SciPy; bootstrap intervals are percentile intervals over resampled subjects. "
        f"Backend: {_BACKEND}."
    )
