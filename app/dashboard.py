"""AcousticBench dashboard entrypoint.

Run from the repository root with::

    PYTHONPATH=src .venv/bin/python -m streamlit run app/dashboard.py

The script configures the page once, renders the branded sidebar with the live
data/results status, and delegates to the selected page through
``st.navigation``.  All heavy data access is cached in
:mod:`app.components.data`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # allow ``import app.*`` regardless of launch cwd
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.components.data import (  # noqa: E402
    get_audit_state,
    get_config,
    get_dataset_state,
    get_results_state,
)
from app.components.theme import (  # noqa: E402
    BRAND_SUBTITLE,
    BRAND_TITLE,
    apply_theme,
    sidebar_brand,
    sidebar_status_line,
)
from app.pages import (  # noqa: E402
    acoustic_feedback,
    data_explorer,
    frequency_response,
    hearing_threshold,
    report_center,
    repeatability,
    signal_laboratory,
    statistical_analysis,
    validation,
)

PAGE_DEFINITIONS = (
    ("1. Data Explorer", "data-explorer", data_explorer.render),
    ("2. Frequency Response", "frequency-response", frequency_response.render),
    ("3. Acoustic Feedback", "acoustic-feedback", acoustic_feedback.render),
    ("4. Repeatability", "repeatability", repeatability.render),
    ("5. Hearing Threshold", "hearing-threshold", hearing_threshold.render),
    ("6. Statistical Analysis", "statistical-analysis", statistical_analysis.render),
    ("7. Signal Laboratory", "signal-laboratory", signal_laboratory.render),
    ("8. Validation", "validation", validation.render),
    ("9. Report Center", "report-center", report_center.render),
)


def _render_sidebar_status() -> None:
    """Sidebar block with data/results availability and environment facts."""
    config = get_config()
    st.sidebar.markdown(
        "<div style='font-size:.7rem;color:#8fa2b1;text-transform:uppercase;"
        "letter-spacing:.14em;margin:.2rem 0 .45rem;'>Workspace status</div>",
        unsafe_allow_html=True,
    )
    dataset_state = get_dataset_state()
    if dataset_state.dataset is not None:
        sidebar_status_line(
            "Dataset",
            f"{dataset_state.size_mb:.0f} MB loaded",
            ok=True,
        )
        sidebar_status_line(
            "Dimensions",
            f"{dataset_state.dataset.frequency_hz.size} \u00d7 {len(dataset_state.dataset.devices)} "
            f"\u00d7 {dataset_state.dataset.subjects.size} \u00d7 {dataset_state.dataset.reinsertions.size}",
            ok=True,
        )
    else:
        sidebar_status_line("Dataset", "not available", ok=False)

    audit_state = get_audit_state()
    if audit_state.audit is not None:
        audit = audit_state.audit
        sidebar_status_line(
            "Data audit",
            f"{len(audit.findings)} checks \u00b7 {audit.n_warnings} warn",
            ok=audit.n_errors == 0,
        )
    else:
        sidebar_status_line("Data audit", "not persisted", ok=None)

    results_state = get_results_state()
    if results_state.results:
        completed = sum(1 for item in results_state.results if item.status == "completed")
        sidebar_status_line(
            "Experiments",
            f"{completed} completed / {len(results_state.results)} saved",
            ok=True,
        )
    else:
        sidebar_status_line("Experiments", "no saved results", ok=False)
    sidebar_status_line("Reports", str(config.reports_dir.name) + "/", ok=None)

    with st.sidebar.expander("Environment", expanded=False):
        st.markdown(
            f"""
- Project: **{config.project.name} {config.project.version}**
- Repository root: `{config.root}`
- Data file: `{config.data_path.name}`
- Results: `{config.results_dir}`
- Reports: `{config.reports_dir}`
- Analysis: alpha {config.analysis.alpha:g}, {config.analysis.correction} correction,
  {config.analysis.bootstrap.n_resamples} bootstrap resamples
- Statistical unit: **{config.analysis.unit_of_analysis}**
            """
        )
        st.caption(
            "Dataset: Denk, Hackenberg & Husstedt (2026), CC BY 4.0. "
            "MATLAB is not available in this environment."
        )


def main() -> None:
    """Configure the page and run the selected dashboard page."""
    st.set_page_config(
        page_title=f"{BRAND_TITLE} \u2014 {BRAND_SUBTITLE}",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "About": (
                f"{BRAND_TITLE} \u2014 {BRAND_SUBTITLE}. "
                "Industrial electroacoustic measurement, validation and reporting toolkit."
            )
        },
    )
    apply_theme()
    sidebar_brand()
    _render_sidebar_status()
    st.sidebar.markdown("---")
    navigation = st.navigation(
        [
            st.Page(render, title=title, url_path=url_path, default=(index == 0))
            for index, (title, url_path, render) in enumerate(PAGE_DEFINITIONS)
        ],
        position="sidebar",
    )
    navigation.run()


if __name__ == "__main__":
    main()
