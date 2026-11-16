"""Visual theme, page chrome and reusable metric components.

The dashboard uses a light content area with a dark-neutral navigation sidebar,
consistent Plotly styling and typography.  No emojis are used: the interface is
intentionally restrained and suitable for an engineering audience.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import streamlit as st

BRAND_TITLE = "AcousticBench"
BRAND_SUBTITLE = "Electroacoustic Measurement, Validation & Reporting Toolkit"

_CSS = """
<style>
:root {
  --acb-bg: #f4f6f8;
  --acb-panel: #ffffff;
  --acb-ink: #1e2a33;
  --acb-muted: #5b6770;
  --acb-accent: #1f77b4;
  --acb-line: #d9e1e8;
  --acb-sidebar: #1b2733;
}
.stApp { background: var(--acb-bg); }
.block-container { padding-top: 2.0rem; padding-bottom: 3.0rem; max-width: 1400px; }
h1, h2, h3, h4 { color: var(--acb-ink); letter-spacing: .1px; }
h1 { font-size: 1.75rem !important; border-bottom: 3px solid var(--acb-accent); padding-bottom: .35rem; }
h2 { font-size: 1.28rem !important; margin-top: 1.2rem !important; }
h3 { font-size: 1.05rem !important; color: var(--acb-accent) !important; }
p, li, label, .stMarkdown { color: var(--acb-ink); }
[data-testid="stSidebar"] {
  background: var(--acb-sidebar);
  border-right: 1px solid #14202a;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] small {
  color: #dbe4ec !important;
}
[data-testid="stSidebar"] hr { border-color: #33434f; }
[data-testid="stSidebar"] [data-baseweb="select"] * { color: #1b2733; }
[data-testid="stSidebar"] input { color: #1b2733; }
.acb-brand { padding: .2rem 0 1.1rem 0; border-bottom: 1px solid #33434f; margin-bottom: 1rem; }
.acb-brand .title { font-size: 1.5rem; font-weight: 700; color: #ffffff; letter-spacing: .4px; }
.acb-brand .subtitle { font-size: .78rem; color: #a9b8c5; line-height: 1.35; margin-top: .25rem; }
.acb-eyebrow { color: var(--acb-muted); text-transform: uppercase; letter-spacing: .14em; font-size: .72rem; font-weight: 600; }
.acb-subtitle { color: var(--acb-muted); font-size: .95rem; margin-top: -.4rem; margin-bottom: 1.1rem; }
.acb-panel { background: var(--acb-panel); border: 1px solid var(--acb-line); border-radius: 8px; padding: 1.0rem 1.2rem; margin: .4rem 0 1.0rem 0; }
.acb-warning { border-left: 4px solid #b06000; background: #fff8ec; padding: .8rem 1rem; border-radius: 4px; margin: .5rem 0 1rem 0; }
.acb-error { border-left: 4px solid #b02a2a; background: #fdf0f0; padding: .8rem 1rem; border-radius: 4px; margin: .5rem 0 1rem 0; }
.acb-info { border-left: 4px solid var(--acb-accent); background: #eff6fb; padding: .8rem 1rem; border-radius: 4px; margin: .5rem 0 1rem 0; }
.acb-note { color: var(--acb-muted); font-size: .84rem; }
div[data-testid="stMetric"] {
  background: var(--acb-panel);
  border: 1px solid var(--acb-line);
  border-radius: 8px;
  padding: .65rem .85rem;
  box-shadow: 0 1px 2px rgba(16,32,48,.04);
}
div[data-testid="stMetricValue"] { font-size: 1.35rem; color: var(--acb-ink); }
div[data-testid="stMetricLabel"] { color: var(--acb-muted); }
.stTabs [data-baseweb="tab-list"] { gap: .35rem; }
.stTabs [data-baseweb="tab"] { border-radius: 6px 6px 0 0; padding: .35rem .8rem; }
[data-testid="stDataFrame"] { border: 1px solid var(--acb-line); border-radius: 6px; }
.stDownloadButton button { border-radius: 6px; }
div[data-testid="stExpander"] { border: 1px solid var(--acb-line); border-radius: 8px; }
</style>
"""


def apply_theme() -> None:
    """Inject the global stylesheet (idempotent on Streamlit reruns)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_brand() -> None:
    """Render the sidebar brand block: product name and tagline."""
    st.sidebar.markdown(
        f"""
        <div class="acb-brand">
          <div class="title">{BRAND_TITLE}</div>
          <div class="subtitle">{BRAND_SUBTITLE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_status_line(label: str, value: str, *, ok: bool | None = None) -> None:
    """Compact status line inside the sidebar."""
    colour = "#8fd19e" if ok else ("#f0b37e" if ok is None else "#e08b8b")
    st.sidebar.markdown(
        f"<div style='font-size:.8rem;color:#c3ced8;display:flex;justify-content:space-between;"
        f"gap:.6rem;padding:.12rem 0;'><span>{label}</span>"
        f"<span style='color:{colour};font-weight:600;text-align:right;'>{value}</span></div>",
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "", *, eyebrow: str = "") -> None:
    """Render the page title block."""
    if eyebrow:
        st.markdown(f"<div class='acb-eyebrow'>{eyebrow}</div>", unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.markdown(f"<div class='acb-subtitle'>{subtitle}</div>", unsafe_allow_html=True)


def section_title(title: str, description: str = "") -> None:
    """Render a section heading with an optional description."""
    st.subheader(title)
    if description:
        st.markdown(f"<div class='acb-note'>{description}</div>", unsafe_allow_html=True)


def metric_cards(items: Sequence[tuple[str, str, str | None]]) -> None:
    """Render a row of metric cards.

    Parameters
    ----------
    items:
        ``(label, value, help)`` triples.  ``help`` may be ``None``.
    """
    columns = st.columns(len(items)) if items else []
    for column, (label, value, help_text) in zip(columns, items):
        with column:
            st.metric(label=label, value=value, help=help_text, border=True)


def info_panel(message: str) -> None:
    st.markdown(f"<div class='acb-info'>{message}</div>", unsafe_allow_html=True)


def warning_panel(message: str, title: str = "Attention") -> None:
    st.markdown(
        f"<div class='acb-warning'><strong>{title}.</strong> {message}</div>",
        unsafe_allow_html=True,
    )


def error_panel(message: str, title: str = "Error") -> None:
    st.markdown(
        f"<div class='acb-error'><strong>{title}.</strong> {message}</div>",
        unsafe_allow_html=True,
    )


def footnote(text: str) -> None:
    st.markdown(f"<div class='acb-note'>{text}</div>", unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """Return an inline HTML badge for an experiment status."""
    normalised = str(status).lower()
    colours = {
        "completed": ("#e3f4e8", "#1d6b35"),
        "failed": ("#fbe4e4", "#9b2222"),
        "skipped": ("#fdf0d8", "#8a5a00"),
    }
    background, foreground = colours.get(normalised, ("#eef2f6", "#33434f"))
    return (
        f"<span style='background:{background};color:{foreground};border-radius:999px;"
        f"padding:2px 10px;font-size:.76rem;font-weight:600;'>{normalised}</span>"
    )


def bullet_list(items: Iterable[str]) -> None:
    st.markdown("\n".join(f"- {item}" for item in items))
