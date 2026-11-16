"""Reusable UI states and result panels.

The helpers here implement the dashboard's error-state policy: whenever a
dataset, result artefact or optional module is missing, the page shows an
explicit, actionable message and keeps rendering the rest of its content
instead of raising an exception.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence, TypeVar

import pandas as pd
import streamlit as st

from acousticbench.data.dataset import AcousticDataset
from acousticbench.experiments.base import ExperimentResult

from app.components.data import DatasetState, get_config, get_dataset_state, optional_module
from app.components.theme import error_panel, footnote, info_panel, status_badge, warning_panel

T = TypeVar("T")

__all__ = [
    "dataset_required",
    "download_frame",
    "ensure_dataset",
    "module_missing_notice",
    "optional_import",
    "result_metrics_frame",
    "result_summary_panel",
    "safe_call",
    "show_dataset_error",
]


# ---------------------------------------------------------------------------
# Dataset availability
# ---------------------------------------------------------------------------
def show_dataset_error(state: DatasetState) -> None:
    """Render the actionable missing-dataset state."""
    config = get_config()
    error_panel(
        f"{state.error}<br/>"
        "The dashboard analyses the measurement dataset at "
        f"<code>{config.data_path}</code>. Place <code>Data.mat</code> at the repository root "
        "and reload the page. The data file is not shipped with the source code; see "
        "<code>DATA_LICENSE.md</code> for its licence and source.",
        title="Measurement dataset unavailable",
    )
    with st.expander("Environment checklist", expanded=False):
        st.markdown(
            f"""
- Repository root: `{config.root}`
- Expected data file: `{config.data_path}` (exists: {config.data_path.is_file()})
- Expected results directory: `{config.results_dir}` (exists: {config.results_dir.is_dir()})
- Expected reports directory: `{config.reports_dir}`
- Launch from the repository root, e.g.
  `PYTHONPATH=src .venv/bin/python -m streamlit run app/dashboard.py`
            """
        )


def ensure_dataset() -> AcousticDataset | None:
    """Return the loaded dataset or render an actionable error and ``None``."""
    state = get_dataset_state()
    if state.dataset is None:
        show_dataset_error(state)
        return None
    return state.dataset


def dataset_required() -> AcousticDataset | None:
    """Alias of :func:`ensure_dataset` kept for readability in pages."""
    return ensure_dataset()


# ---------------------------------------------------------------------------
# Safe analysis calls
# ---------------------------------------------------------------------------
def safe_call(function: Callable[..., T], *args: Any, **kwargs: Any) -> tuple[T | None, str | None]:
    """Call ``function``; return ``(value, error_message)`` instead of raising."""
    try:
        return function(*args, **kwargs), None
    except Exception as exc:  # noqa: BLE001 - pages render the message
        return None, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Optional modules
# ---------------------------------------------------------------------------
def optional_import(module_name: str, *, feature: str = "") -> Any | None:
    """Import an optional module or render a clear "not yet available" notice."""
    module, error = optional_module(module_name)
    if module is None:
        label = feature or module_name
        warning_panel(
            f"{label} is not available in this checkout (<code>{module_name}</code> could not be "
            f"imported: {error}). This section is disabled until the module is present; run the "
            "experiments/tests after it has been added.",
            title="Module not yet available",
        )
        return None
    return module


def module_missing_notice(module_name: str, feature: str) -> None:
    """Render a standard module-missing notice."""
    warning_panel(
        f"{feature} requires the optional module <code>{module_name}</code>, which could not be "
        "imported in this environment. Install the project dependencies and run the test suite.",
        title="Module not yet available",
    )


# ---------------------------------------------------------------------------
# Saved result panels
# ---------------------------------------------------------------------------
def _flatten_metrics(metrics: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, value in metrics.items():
        label = f"{prefix}{key}"
        if isinstance(value, dict):
            rows.extend(_flatten_metrics(value, prefix=f"{label} \u00b7 "))
        else:
            rows.append((label, _format_metric(value)))
    return rows


def _format_metric(value: Any) -> str:
    if value is None:
        return "\u2014"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, (list, tuple)):
        text = ", ".join(_format_metric(item) for item in value[:6])
        return text + (" \u2026" if len(value) > 6 else "")
    return str(value)


def result_metrics_frame(result: ExperimentResult) -> pd.DataFrame:
    """Flatten an experiment's nested metrics into a two-column frame."""
    rows = _flatten_metrics(result.metrics or {})
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def result_summary_panel(
    result: ExperimentResult | None,
    *,
    code: str,
    title: str = "",
    expanded: bool = False,
) -> None:
    """Render the persisted result of one experiment as a summary panel.

    Shows a status line, metrics table, narrative and warnings, or an
    actionable "not yet available" notice when the result is missing.
    """
    from acousticbench.experiments.base import ExperimentResult as _Result  # noqa: F401

    if result is None:
        info_panel(
            f"Persisted results for <strong>{code}</strong>"
            + (f" ({title})" if title else "")
            + " are not available yet. The page above already shows a live analysis computed "
            "from <code>Data.mat</code>; the persisted experiment summary appears here once the "
            "experiment has been run and saved under <code>results/experiments/</code>."
        )
        return
    with st.expander(
        f"{code} \u2014 {result.title}: persisted result summary",
        expanded=expanded,
    ):
        st.markdown(
            f"{status_badge(result.status)} &nbsp; "
            f"<span style='color:#5b6770;font-size:.86rem;'>Runtime {result.duration_s:.2f} s "
            f"\u00b7 {len(result.tables)} tables \u00b7 {len(getattr(result, 'figure_paths', {}) or {})} figures</span>",
            unsafe_allow_html=True,
        )
        if result.error:
            error_panel(result.error, title="Experiment error")
        if result.warnings:
            for warning in result.warnings:
                warning_panel(warning, title="Experiment warning")
        metrics = result_metrics_frame(result)
        if not metrics.empty:
            st.dataframe(metrics, width="stretch", hide_index=True, height=min(420, 36 + 30 * len(metrics)))
        if result.narrative:
            st.markdown("**Narrative**")
            st.markdown(result.narrative)
        figure_paths = getattr(result, "figure_paths", {}) or {}
        if figure_paths:
            st.markdown("**Persisted figures**")
            names = sorted(figure_paths)
            columns = st.columns(min(3, len(names)))
            for index, name in enumerate(names):
                with columns[index % len(columns)]:
                    st.image(str(figure_paths[name]), caption=name, width="stretch")
        elif result.tables:
            st.markdown("**Persisted tables**")
            for name, frame in result.tables.items():
                st.markdown(f"`{name}` ({len(frame)} rows \u00d7 {len(frame.columns)} columns)")
        footnote("Loaded from the persisted experiment artefacts; no analysis was re-run.")


def download_frame(frame: pd.DataFrame, filename: str, label: str = "Download CSV") -> None:
    """Render a CSV download button for a frame."""
    if frame is None or frame.empty:
        return
    st.download_button(
        label=label,
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        width="content",
        key=f"download_{filename}",
    )


def experiment_status_frame(results: Sequence[ExperimentResult | None]) -> pd.DataFrame:
    """Build a status table for the Validation page."""
    rows = []
    for result in results:
        if result is None:
            continue
        rows.append(
            {
                "Code": result.code,
                "Title": result.title,
                "Status": result.status,
                "Runtime [s]": round(float(result.duration_s), 2),
                "Tables": len(result.tables),
                "Figures": len(getattr(result, "figure_paths", {}) or {}),
                "Warnings": len(result.warnings),
                "Error": result.error or "",
            }
        )
    return pd.DataFrame(rows)
