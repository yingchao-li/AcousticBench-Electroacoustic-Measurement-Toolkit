"""Page 9 — Report Center.

Select persisted experiments and report options, generate a PDF/Excel/HTML
report on demand through :mod:`acousticbench.report.builder`, show the
generation metadata and provide download buttons for the generated and
existing reports.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from acousticbench.report import build_all_reports, report_metadata
from app.components import theme, ui
from app.components.data import get_config, get_results_state, get_saved_audit_for_report

TITLE = "Report Center"
SUBTITLE = (
    "Generate professional PDF, Excel and HTML reports from the persisted experiments, "
    "with the data audit, provenance, figures and limitations."
)

_FORMAT_LABELS = {
    "pdf": "PDF (reportlab, embedded figures)",
    "excel": "Excel (multi-sheet workbook)",
    "html": "HTML (self-contained, base64 figures)",
}
_SUFFIX_TO_FORMAT = {".pdf": "pdf", ".xlsx": "excel", ".html": "html"}


def _human_size(size_bytes: int | float) -> str:
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _existing_reports(reports_dir: Path) -> list[Path]:
    if not reports_dir.is_dir():
        return []
    files = [
        path
        for path in reports_dir.iterdir()
        if path.is_file() and path.suffix.lower() in _SUFFIX_TO_FORMAT
    ]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files


def _download(path: Path, *, label: str) -> None:
    """Render a download button for an existing report file."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        theme.error_panel(f"Cannot read {path.name}: {exc}")
        return
    st.download_button(
        label=label,
        data=data,
        file_name=path.name,
        mime={
            "pdf": "application/pdf",
            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "html": "text/html",
        }.get(_SUFFIX_TO_FORMAT.get(path.suffix.lower(), ""), "application/octet-stream"),
        key=f"rc_download_{path.name}",
        width="content",
    )


def _render_generated(metadata: dict[str, dict]) -> None:
    if not metadata:
        return
    theme.section_title(
        "Generated reports",
        "Files written to the configured reports directory; use the buttons to download them.",
    )
    rows = []
    for format_name, info in metadata.items():
        rows.append(
            {
                "Format": format_name.upper(),
                "File": info.get("name", ""),
                "Size": _human_size(info.get("size_bytes", 0)),
                "Modified": info.get("modified", ""),
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    columns = st.columns(len(metadata))
    for column, (format_name, info) in zip(columns, metadata.items()):
        with column:
            path = Path(info.get("path", ""))
            theme.footnote(f"**{format_name.upper()}** \u00b7 {_human_size(info.get('size_bytes', 0))}")
            if path.is_file():
                _download(path, label=f"Download {format_name.upper()}")


def render() -> None:
    """Render the Report Center page."""
    theme.page_header(TITLE, SUBTITLE, eyebrow="Reporting")
    config = get_config()
    results_state = get_results_state()
    reports_dir = config.reports_dir
    existing = _existing_reports(reports_dir)
    audit = get_saved_audit_for_report()

    theme.metric_cards(
        [
            ("Saved experiments", str(len(results_state.results)), "Available as report content."),
            ("Experiments completed", str(sum(1 for item in results_state.results if item.status == "completed")), None),
            ("Persisted audit", "available" if audit is not None else "not available", "Included optionally."),
            ("Existing reports", str(len(existing)), f"Directory: {reports_dir}"),
        ]
    )

    if results_state.error:
        theme.warning_panel(results_state.error, title="Result loading warning")
    if not results_state.results:
        theme.error_panel(
            "No persisted experiment results are available. Run at least one experiment so that "
            "<code>results/experiments/*/result.json</code> exists, then return to this page.",
            title="Nothing to report",
        )
        _render_existing(existing, reports_dir)
        return

    by_code = results_state.by_code
    options = [result.code for result in results_state.results]
    default_selection = [
        code for code in ("E01", "E02") if code in by_code
    ] or options[: min(2, len(options))]
    labels = {
        result.code: f"{result.code} \u2014 {result.title} ({result.status})"
        for result in results_state.results
    }

    theme.section_title("1. Select report content")
    selected_codes = st.multiselect(
        "Experiments to include",
        options=options,
        default=default_selection,
        format_func=lambda code: labels.get(code, code),
        key="rc_experiments",
        help="Only persisted results are available here; run experiments first to extend the list.",
    )
    column_left, column_right = st.columns([3, 2])
    with column_left:
        selected_formats = st.multiselect(
            "Formats",
            options=["pdf", "excel", "html"],
            default=["pdf", "excel", "html"],
            format_func=lambda value: _FORMAT_LABELS.get(value, value),
            key="rc_formats",
        )
    with column_right:
        include_audit = st.checkbox(
            "Include the persisted data audit",
            value=audit is not None,
            disabled=audit is None,
            key="rc_include_audit",
            help="The audit adds a data-quality section to every report format."
            if audit is not None
            else "No persisted audit (results/audit/data_audit.json) was found.",
        )
    if selected_codes:
        included = [by_code[code] for code in selected_codes]
        st.caption(
            "Content: "
            + ", ".join(f"{result.code} ({len(result.tables)} tables, "
                        f"{len(getattr(result, 'figure_paths', {}) or {})} figures)" for result in included)
            + f". Output directory: `{reports_dir}`."
        )

    theme.section_title("2. Generate")
    theme.footnote(
        "Generation embeds the persisted PNG figures and the first rows of every table; "
        "a multi-experiment Excel workbook can be large, so generation may take a few seconds."
    )
    generate_disabled = not selected_codes or not selected_formats
    if st.button(
        "Generate reports",
        type="primary",
        disabled=generate_disabled,
        key="rc_generate",
    ):
        with st.spinner("Building the requested report formats ..."):
            try:
                paths = build_all_reports(
                    [by_code[code] for code in selected_codes],
                    reports_dir,
                    config=config,
                    audit=audit if include_audit else None,
                    formats=tuple(selected_formats),
                )
            except Exception as exc:  # noqa: BLE001 - the UI renders the message
                theme.error_panel(f"Report generation failed: {exc}", title="Generation failed")
                st.session_state.pop("rc_generated", None)
            else:
                metadata = report_metadata(paths)
                st.session_state["rc_generated"] = metadata
                st.success(
                    f"Generated {len(paths)} report file(s) in {reports_dir}."
                )
    if generate_disabled:
        st.caption("Select at least one experiment and one format to enable report generation.")

    generated = st.session_state.get("rc_generated")
    if generated:
        _render_generated(generated)

    theme.section_title("3. Existing reports")
    _render_existing(existing, reports_dir)

    theme.footnote(
        "Reports are generated from persisted artefacts only: no analysis is recomputed and no "
        "result is fabricated during report generation. MATLAB is not available in this "
        "environment, so cross-language agreement (E15) is reported as unverified."
    )


def _render_existing(existing: list[Path], reports_dir: Path) -> None:
    """Render the table and download controls of existing report files."""
    if not existing:
        theme.info_panel(
            f"No reports exist yet in <code>{reports_dir}</code>. Generate one above; the files "
            "appear here for later download."
        )
        return
    rows = []
    for path in existing:
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append(
            {
                "File": path.name,
                "Format": _SUFFIX_TO_FORMAT.get(path.suffix.lower(), "").upper(),
                "Size": _human_size(stat.st_size),
                "Modified": pd.Timestamp(stat.st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    with st.expander("Download existing reports", expanded=False):
        for path in existing:
            columns = st.columns([4, 1])
            with columns[0]:
                st.markdown(f"`{path.name}`")
            with columns[1]:
                _download(path, label="Download")
