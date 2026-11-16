"""PDF report generation (reportlab platypus).

The builder consumes :class:`~acousticbench.experiments.base.ExperimentResult`
objects and the *persisted* artefacts (PNG figures, CSV tables).  It never
re-runs an analysis: what is written in the report is exactly what the
experiment produced.

Layout
------
1. title page (project, organisation, generation timestamp, dataset provenance),
2. table of contents,
3. data-quality audit summary (when an audit is supplied),
4. one section per experiment: status, metrics table, narrative, figures,
   first rows of every table,
5. limitations page,
6. MATLAB verification status.

The function is robust to missing tables/figures and to individual reportlab
conversion errors: a problem with one artefact is reported inline instead of
aborting the whole document.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from acousticbench.config import Config, load_config
from acousticbench.data.audit import DataAudit
from acousticbench.exceptions import ReportError
from acousticbench.experiments.base import ExperimentResult

__all__ = ["build_pdf_report"]

_ACCENT = colors.HexColor("#1f77b4")
_DARK = colors.HexColor("#22303c")
_MUTED = colors.HexColor("#5b6770")
_LIGHT = colors.HexColor("#eef2f6")
_WARN = colors.HexColor("#b06000")

_MAX_TABLE_ROWS = 12
_MAX_TABLE_COLUMNS = 8
_MAX_METRIC_ROWS = 60
_MAX_CELL_CHARS = 90


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ABTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=26,
            leading=31, textColor=_DARK, alignment=TA_CENTER, spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "ABSubtitle", parent=base["Normal"], fontName="Helvetica", fontSize=13,
            leading=17, textColor=_MUTED, alignment=TA_CENTER, spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "ABH1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16,
            leading=20, textColor=_DARK, spaceBefore=6, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "ABH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12,
            leading=15, textColor=_ACCENT, spaceBefore=10, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "ABBody", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2,
            leading=13, textColor=colors.HexColor("#1b1b1b"), alignment=TA_JUSTIFY,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "ABSmall", parent=base["BodyText"], fontName="Helvetica", fontSize=8,
            leading=10.5, textColor=_MUTED, spaceAfter=3,
        ),
        "cell": ParagraphStyle(
            "ABCell", parent=base["BodyText"], fontName="Helvetica", fontSize=7.2,
            leading=9, textColor=colors.HexColor("#1b1b1b"),
        ),
        "cellbold": ParagraphStyle(
            "ABCellBold", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.2,
            leading=9, textColor=colors.white,
        ),
        "caption": ParagraphStyle(
            "ABCaption", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=7.8,
            leading=10, textColor=_MUTED, spaceBefore=2, spaceAfter=8,
        ),
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _format_value(value: Any, max_chars: int = _MAX_CELL_CHARS) -> str:
    """Format an arbitrary metric/table value for display."""
    if value is None:
        return "\u2014"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "\u2014"
        if value == int(value) and abs(value) < 1e9:
            return f"{int(value)}"
        return f"{value:.4g}"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, (list, tuple)):
        inner = ", ".join(_format_value(item, 40) for item in value[:6])
        if len(value) > 6:
            inner += ", \u2026"
        return inner
    if isinstance(value, dict):
        parts = [f"{key}: {_format_value(item, 40)}" for key, item in list(value.items())[:6]]
        return "; ".join(parts)
    text = str(value)
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "\u2026"
    return text


def _safe_markup(text: str) -> str:
    """Escape text for reportlab Paragraph and preserve paragraph breaks."""
    return escape(str(text)).replace("\n", "<br/>")


def _metric_rows(metrics: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Flatten a nested metrics mapping into ``(label, formatted value)`` rows."""
    rows: list[tuple[str, str]] = []
    for key, value in metrics.items():
        label = f"{prefix}{key}"
        if isinstance(value, dict):
            rows.extend(_metric_rows(value, prefix=f"{label} \u00b7 "))
        else:
            rows.append((label, _format_value(value)))
        if len(rows) >= _MAX_METRIC_ROWS:
            rows = rows[:_MAX_METRIC_ROWS]
            rows.append(("\u2026", "additional metrics omitted"))
            break
    return rows


def _data_table(
    rows: Iterable[Sequence[Any]],
    *,
    styles: dict[str, ParagraphStyle],
    available_width: float,
    header: bool = True,
) -> Table | None:
    """Build a styled platypus table from rows (first row = header)."""
    matrix = [list(row) for row in rows]
    if not matrix:
        return None
    n_columns = max(len(row) for row in matrix)
    matrix = [row + [""] * (n_columns - len(row)) for row in matrix]
    column_width = available_width / n_columns
    header_style = styles["cellbold"]
    data_style = styles["cell"]
    wrapped = []
    for row_index, row in enumerate(matrix):
        style = header_style if (header and row_index == 0) else data_style
        wrapped.append([Paragraph(_safe_markup(_format_value(cell)), style) for cell in row])
    table = Table(wrapped, colWidths=[column_width] * n_columns, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d3dc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
            ]
        )
    else:
        commands.append(("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _LIGHT]))
    table.setStyle(TableStyle(commands))
    return table


def _frame_table(frame: Any, styles: dict[str, ParagraphStyle], available_width: float) -> list[Any]:
    """Convert the first rows of a DataFrame into reportlab flowables."""
    flowables: list[Any] = []
    try:
        import pandas as pd  # local import keeps module import light

        if not isinstance(frame, pd.DataFrame) or frame.empty:
            return flowables
        preview = frame.iloc[:_MAX_TABLE_ROWS, :_MAX_TABLE_COLUMNS].copy()
        for column in preview.columns:
            preview[column] = preview[column].map(_format_value)
        rows = [list(preview.columns.astype(str))] + preview.astype(str).values.tolist()
        table = _data_table(rows, styles=styles, available_width=available_width)
        if table is not None:
            flowables.append(table)
        omitted_columns = max(0, len(frame.columns) - _MAX_TABLE_COLUMNS)
        omitted_rows = max(0, len(frame) - _MAX_TABLE_ROWS)
        note_bits = []
        if omitted_rows:
            note_bits.append(f"{omitted_rows} further rows")
        if omitted_columns:
            note_bits.append(f"{omitted_columns} further columns")
        note = "First rows shown" + (f" ({', '.join(note_bits)} omitted)" if note_bits else "")
        flowables.append(Paragraph(note, styles["caption"]))
    except Exception as exc:  # noqa: BLE001 - one bad table must not kill the report
        flowables.append(Paragraph(f"Table could not be rendered: {_safe_markup(str(exc))}", styles["small"]))
    return flowables


def _embed_figure(path: Path, styles: dict[str, ParagraphStyle], available_width: float) -> list[Any]:
    """Embed one persisted PNG figure, scaled to the text frame."""
    flowables: list[Any] = []
    try:
        reader = ImageReader(str(path))
        width, height = reader.getSize()
        if width <= 0 or height <= 0:
            raise ValueError("invalid image size")
        scale = min(available_width / width, (170 * mm) / height)
        draw_width, draw_height = width * scale, height * scale
        flowables.append(Image(str(path), width=draw_width, height=draw_height))
        flowables.append(Paragraph(_safe_markup(path.stem), styles["caption"]))
    except Exception as exc:  # noqa: BLE001 - missing/corrupt figure is non-fatal
        flowables.append(
            Paragraph(
                f"Figure {_safe_markup(path.name)} could not be embedded: {_safe_markup(str(exc))}",
                styles["small"],
            )
        )
    return flowables


# ---------------------------------------------------------------------------
# Page decoration
# ---------------------------------------------------------------------------
def _page_size(name: str) -> tuple[float, float]:
    return LETTER if str(name).strip().lower().startswith("letter") else A4


def _make_page_decorator(title: str):
    def decorate(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        width, height = doc.pagesize
        canvas.setStrokeColor(colors.HexColor("#d5dde4"))
        canvas.setLineWidth(0.6)
        canvas.line(18 * mm, height - 15 * mm, width - 18 * mm, height - 15 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_MUTED)
        canvas.drawString(18 * mm, height - 12 * mm, title)
        canvas.drawRightString(width - 18 * mm, height - 12 * mm, "AcousticBench")
        canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
        canvas.drawString(18 * mm, 9 * mm, "Generated report \u2014 AcousticBench")
        canvas.drawRightString(width - 18 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    return decorate


# ---------------------------------------------------------------------------
# Content sections
# ---------------------------------------------------------------------------
def _title_page(
    story: list[Any],
    *,
    config: Config,
    audit: DataAudit | None,
    results: Sequence[ExperimentResult],
    styles: dict[str, ParagraphStyle],
    available_width: float,
) -> None:
    story.append(Spacer(1, 38 * mm))
    story.append(Paragraph(_safe_markup(config.report.title), styles["title"]))
    story.append(
        Paragraph(_safe_markup(config.project.description or config.dashboard.subtitle), styles["subtitle"])
    )
    story.append(Spacer(1, 10 * mm))
    organisation = config.report.organisation or config.project.name
    provenance_rows = [
        ["Field", "Value"],
        ["Organisation", organisation],
        ["Project", f"{config.project.name} {config.project.version}"],
        ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Experiments", ", ".join(f"{item.code} {item.title}" for item in results)],
        ["Report formats", "PDF (this document), Excel, HTML"],
    ]
    if audit is not None and audit.dataset_summary:
        file_info = audit.dataset_summary.get("file", {}) or {}
        provenance_rows.extend(
            [
                ["Dataset", Path(str(file_info.get("path", "Data.mat"))).name],
                ["Dataset size", f"{float(file_info.get('size_mb', 0.0)):.1f} MB"],
                ["MAT format", str(file_info.get("mat_format", "\u2014"))],
                ["SHA-256", str(file_info.get("sha256", "\u2014"))],
            ]
        )
    table = _data_table(
        provenance_rows,
        styles=styles,
        available_width=available_width,
    )
    if table is not None:
        story.append(table)
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "This report was generated automatically from persisted experiment artefacts. "
            "No analysis result was fabricated, re-estimated or imputed during report generation.",
            styles["small"],
        )
    )
    story.append(PageBreak())


def _contents_page(
    story: list[Any], results: Sequence[ExperimentResult], styles: dict[str, ParagraphStyle]
) -> None:
    story.append(Paragraph("Contents", styles["h1"]))
    lines = [
        "1. Data quality audit",
        "2. Experiment results",
    ]
    lines.extend(f"   {item.code} \u2014 {item.title}" for item in results)
    lines.append("3. Limitations and interpretation")
    lines.append("4. MATLAB verification status")
    for line in lines:
        story.append(Paragraph(_safe_markup(line), styles["body"]))
    story.append(PageBreak())


def _audit_section(
    story: list[Any],
    audit: DataAudit,
    *,
    styles: dict[str, ParagraphStyle],
    available_width: float,
) -> None:
    story.append(Paragraph(f"Data quality audit \u2014 {audit.generated_at or 'timestamp unavailable'}", styles["h1"]))
    story.append(
        Paragraph(
            f"{sum(1 for item in audit.findings if item.status == 'PASS')} passed, "
            f"{audit.n_warnings} warnings, {audit.n_errors} errors across "
            f"{len(audit.findings)} automated checks. The audit is loaded from the persisted "
            "artefact <i>results/audit/data_audit.json</i>.",
            styles["body"],
        )
    )
    variables = audit.variables
    if variables is not None and not variables.empty:
        columns = [
            column
            for column in ("key", "shape", "dtype", "n_nan", "nan_fraction", "median_level_db", "unit")
            if column in variables.columns
        ]
        if columns:
            story.append(Paragraph("Datasets and variables", styles["h2"]))
            story.extend(_frame_table(variables[columns], styles, available_width))

    validity = audit.session_validity
    if validity is not None and not validity.empty:
        story.append(Paragraph("Session validity (measured NaNs)", styles["h2"]))
        story.extend(_frame_table(validity, styles, available_width))
        invalid = audit.invalid_sessions
        story.append(
            Paragraph(
                f"{0 if invalid is None else len(invalid)} (container, device, subject, reinsertion) "
                "sessions are completely NaN; they are excluded from every analysis and never imputed.",
                styles["body"],
            )
        )

    checks = audit.checks_frame()
    if not checks.empty:
        story.append(Paragraph("Automated checks", styles["h2"]))
        story.extend(_frame_table(checks, styles, available_width))

    structural = audit.structural_validity
    if structural is not None and not structural.empty:
        columns = [
            column
            for column in (
                "container",
                "description",
                "valid_conditions",
                "valid_couplings",
                "n_structurally_valid_devices",
                "valid_device_codes",
            )
            if column in structural.columns
        ]
        if columns:
            story.append(Paragraph("Structural validity rules", styles["h2"]))
            story.extend(_frame_table(structural[columns], styles, available_width))
    story.append(PageBreak())


def _experiment_section(
    story: list[Any],
    result: ExperimentResult,
    *,
    styles: dict[str, ParagraphStyle],
    available_width: float,
) -> None:
    heading = f"{result.code} \u2014 {result.title}"
    status_line = (
        f"<b>Status:</b> {_safe_markup(result.status)} &nbsp;&nbsp; "
        f"<b>Runtime:</b> {result.duration_s:.2f} s &nbsp;&nbsp; "
        f"<b>Tables:</b> {len(result.tables)} &nbsp;&nbsp; "
        f"<b>Figures:</b> {len(getattr(result, 'figure_paths', {}) or {})}"
    )
    story.append(KeepTogether([Paragraph(_safe_markup(heading), styles["h1"]), Paragraph(status_line, styles["body"])]))

    if result.error:
        story.append(Paragraph(f"<b>Error:</b> {_safe_markup(result.error)}", styles["body"]))
    if result.warnings:
        story.append(Paragraph("Warnings", styles["h2"]))
        for warning in result.warnings:
            story.append(Paragraph(f"\u2022 {_safe_markup(warning)}", styles["small"]))

    if result.narrative:
        story.append(Paragraph("Summary", styles["h2"]))
        paragraphs = [item.strip() for item in str(result.narrative).split("\n\n") if item.strip()]
        for paragraph in paragraphs[:12]:
            if paragraph.startswith("#"):
                continue
            story.append(Paragraph(_safe_markup(paragraph), styles["body"]))

    if result.metrics:
        story.append(Paragraph("Metrics", styles["h2"]))
        rows = _metric_rows(result.metrics)
        table = _data_table(
            [("Metric", "Value")] + rows, styles=styles, available_width=available_width
        )
        if table is not None:
            story.append(table)
        story.append(Spacer(1, 3 * mm))

    figure_paths = getattr(result, "figure_paths", {}) or {}
    story.append(Paragraph("Figures", styles["h2"]))
    if figure_paths:
        for name, path in sorted(figure_paths.items()):
            story.append(Paragraph(_safe_markup(str(name)), styles["caption"]))
            story.extend(_embed_figure(Path(path), styles, available_width))
    else:
        story.append(Paragraph("No figure was persisted for this experiment.", styles["small"]))

    if result.tables:
        story.append(Paragraph("Tables (first rows)", styles["h2"]))
        for name, frame in result.tables.items():
            story.append(Paragraph(_safe_markup(f"{name} ({len(frame)} rows \u00d7 {len(frame.columns)} columns)"), styles["h2"]))
            story.extend(_frame_table(frame, styles, available_width))
    else:
        story.append(Paragraph("No table was persisted for this experiment.", styles["small"]))
    story.append(PageBreak())


def _limitations_section(
    story: list[Any], *, config: Config, styles: dict[str, ParagraphStyle]
) -> None:
    story.append(Paragraph("Limitations and interpretation", styles["h1"]))
    bootstrap = config.analysis.bootstrap
    paragraphs = [
        "The measurement dataset is observational: the 14 subjects are not a random sample of a "
        "clinical population, and all statements are descriptive of this study sample.",
        "The subject is the independent statistical unit. Reinsertions are technical repeats and "
        "are averaged within subject before any inferential comparison.",
        f"Inferential statements use alpha = {config.analysis.alpha:g}, {config.analysis.correction} "
        f"multiple-comparison correction and {bootstrap.n_resamples} bootstrap resamples "
        f"(confidence {bootstrap.confidence:.0%}, seed {bootstrap.seed}, {bootstrap.method} method).",
        "Measured NaNs are excluded and structurally invalid entries (documented as physically "
        "meaningless for the analysed quantity) are masked; no value is imputed anywhere.",
        "Audiometric thresholds are quantised to 1 dB, which limits the resolution of threshold-based "
        "effect estimates and may hide sub-dB effects.",
        "Transfer-function levels are reported in dB SPL at the fixed 11.2 mV receiver drive; they "
        "are not equal to an in-situ speech level or to a prescribed gain target.",
        "Figures and tables are reproduced exactly from the persisted experiment artefacts; they were "
        "not recomputed for the report and may therefore lag behind a newer data file.",
    ]
    for paragraph in paragraphs:
        story.append(Paragraph(_safe_markup(paragraph), styles["body"]))
    story.append(PageBreak())


def _matlab_status_section(
    story: list[Any], *, styles: dict[str, ParagraphStyle], result_codes: set[str]
) -> None:
    story.append(Paragraph("MATLAB verification status", styles["h1"]))
    story.append(
        Paragraph(
            "<b>MATLAB is not available in this environment.</b> The cross-language consistency "
            "check (experiment E15) could not be executed, so numerical agreement between the "
            "original MATLAB reference implementation and this Python implementation is "
            "<b>not verified</b> by this report.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "All Python results shown here were produced and validated against the dataset's "
            "documented structural properties and the persisted data audit; they are not a "
            "MATLAB-verified reproduction claim.",
            styles["body"],
        )
    )
    if "E15" in result_codes:
        story.append(
            Paragraph(
                "An E15 result is present in the results directory; check its status carefully: a "
                "skipped status indicates that MATLAB was unavailable when it ran.",
                styles["body"],
            )
        )
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Report generated by AcousticBench \u2014 Electroacoustic Measurement, Validation & "
            "Reporting Toolkit.",
            styles["small"],
        )
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_pdf_report(
    results: Sequence[ExperimentResult],
    output_path: str | Path,
    *,
    config: Config | None = None,
    audit: DataAudit | None = None,
) -> Path:
    """Build a multi-page PDF report from experiment results.

    Parameters
    ----------
    results:
        Experiment results in presentation order (each must expose ``code``,
        ``title``, ``metrics``, ``tables``, optional ``figure_paths``).
    output_path:
        Destination ``.pdf`` path; parent directories are created.
    config:
        Configuration supplying the report title, organisation and page size.
    audit:
        Optional persisted :class:`~acousticbench.data.audit.DataAudit`.

    Returns
    -------
    Path
        The written PDF path.

    Raises
    ------
    ReportError
        If no results are supplied or the document cannot be built.
    """
    from acousticbench.report.builder import SavedExperimentResult  # noqa: F401  (contract check)

    cfg = config or load_config()
    sequence = list(results)
    if not sequence:
        raise ReportError("build_pdf_report requires at least one experiment result")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    page_size = _page_size(cfg.report.page_size)
    margin = 18 * mm
    frame_width = page_size[0] - 2 * margin

    try:
        doc = BaseDocTemplate(
            str(destination),
            pagesize=page_size,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=22 * mm,
            bottomMargin=18 * mm,
            title=f"{cfg.report.title} \u2014 {datetime.now():%Y-%m-%d %H:%M}",
            author=cfg.report.organisation or cfg.project.name,
            subject="AcousticBench automated measurement report",
            creator="AcousticBench",
        )
        frame = Frame(
            margin,
            18 * mm,
            frame_width,
            page_size[1] - 22 * mm - 18 * mm,
            id="content",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        decorator = _make_page_decorator(cfg.report.title)
        doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=decorator)])

        story: list[Any] = []
        _title_page(
            story,
            config=cfg,
            audit=audit,
            results=sequence,
            styles=styles,
            available_width=frame_width,
        )
        _contents_page(story, sequence, styles)
        if audit is not None:
            _audit_section(story, audit, styles=styles, available_width=frame_width)
        else:
            story.append(Paragraph("Data quality audit", styles["h1"]))
            story.append(
                Paragraph(
                    "No persisted data audit (<i>results/audit/data_audit.json</i>) was available "
                    "when this report was generated. Run the data audit to include the "
                    "data-quality summary in future reports.",
                    styles["body"],
                )
            )
            story.append(PageBreak())

        for result in sequence:
            try:
                _experiment_section(
                    story, result, styles=styles, available_width=frame_width
                )
            except Exception as exc:  # noqa: BLE001 - one section must not kill the report
                story.append(
                    Paragraph(
                        f"Experiment {_safe_markup(getattr(result, 'code', '?'))} could not be "
                        f"rendered: {_safe_markup(str(exc))}",
                        styles["body"],
                    )
                )
                story.append(PageBreak())

        _limitations_section(story, config=cfg, styles=styles)
        _matlab_status_section(
            story, styles=styles, result_codes={item.code for item in sequence}
        )
        doc.build(story)
    except ReportError:
        raise
    except Exception as exc:  # noqa: BLE001 - wrap reportlab failures with context
        raise ReportError(f"PDF report generation failed: {exc}") from exc

    if not destination.is_file() or destination.stat().st_size == 0:
        raise ReportError(f"PDF report was not written: {destination}")
    return destination
