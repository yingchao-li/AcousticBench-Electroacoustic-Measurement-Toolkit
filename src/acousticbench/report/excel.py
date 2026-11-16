"""Excel report generation (xlsxwriter).

Workbook layout
---------------
``Summary``
    Report metadata, experiment index and artefact counts.
``Data Audit``
    Audit summary, automated checks, variables, session validity and
    structural validity rules (when an audit is supplied).
``Statistics``
    Long-format table of every scalar metric of every experiment, suitable for
    pivot tables.
``<experiment table>``
    One sheet per ``result.tables[name]``, sanitised to Excel's 31-character
    sheet-name limit with de-duplicated names.

The writer is robust to missing tables, empty frames and NaN/inf values
(written as an en dash placeholder) and applies professional formatting:
bold coloured headers, frozen panes, sensible column widths and numeric
formats.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

from acousticbench.config import Config, load_config
from acousticbench.data.audit import DataAudit
from acousticbench.exceptions import ReportError
from acousticbench.experiments.base import ExperimentResult

__all__ = ["build_excel_report"]

_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
_MAX_SHEET_NAME = 31
#: Row cap per experiment table sheet (the full table stays on disk as CSV).
_MAX_SHEET_ROWS = 500
_PLACEHOLDER = "\u2014"


def _safe_table_filename(name: str) -> str:
    """Reproduce the experiment runner's table file-name sanitisation."""
    return "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in str(name)
    ).strip("_")


def _frame_digest(frame: pd.DataFrame) -> str:
    """Stable digest used to skip duplicate table sheets."""
    try:
        hashed = pd.util.hash_pandas_object(frame, index=False).to_numpy()
        payload = f"{frame.shape}|{list(frame.columns)}|".encode("utf-8") + hashed.tobytes()
    except Exception:  # noqa: BLE001 - fall back to a shape/column digest
        return f"{frame.shape}|{list(frame.columns)}"
    return hashlib.sha1(payload).hexdigest()


def _full_table_hint(result: ExperimentResult, table_name: str) -> str:
    """Human-readable on-disk location of the uncapped table file."""
    directory = getattr(result, "directory", None)
    table_paths = getattr(result, "table_paths", {}) or {}
    actual_path = table_paths.get(table_name)
    if directory is not None:
        file_name = (
            Path(actual_path).name
            if actual_path is not None
            else f"{_safe_table_filename(table_name)}.csv"
        )
        return f"results/experiments/{Path(directory).name}/tables/{file_name}"
    safe_name = _safe_table_filename(table_name)
    return f"results/experiments/<{result.code} experiment directory>/tables/{safe_name}.csv"


def _sanitize_sheet_name(name: str, used: set[str]) -> str:
    """Return a valid, unique Excel worksheet name (``<= 31`` characters)."""
    cleaned = _INVALID_SHEET_CHARS.sub("_", str(name)).strip().strip("'")
    cleaned = re.sub(r"\s+", " ", cleaned) or "Sheet"
    cleaned = cleaned[:_MAX_SHEET_NAME]
    candidate = cleaned
    counter = 2
    while candidate.casefold() in used:
        suffix = f" ({counter})"
        candidate = f"{cleaned[: _MAX_SHEET_NAME - len(suffix)]}{suffix}"
        counter += 1
    used.add(candidate.casefold())
    return candidate


def _excel_value(value: Any) -> Any:
    """Convert a Python/NumPy value into something xlsxwriter can write."""
    if value is None:
        return _PLACEHOLDER
    if isinstance(value, float):
        return value if math.isfinite(value) else _PLACEHOLDER
    if hasattr(value, "item"):
        try:
            return _excel_value(value.item())
        except (ValueError, TypeError):
            pass
    if isinstance(value, (int, str, bool)):
        return value
    if isinstance(value, (datetime,)):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _stringify(value: Any, max_chars: int = 200) -> str:
    if isinstance(value, float) and not math.isfinite(value):
        return _PLACEHOLDER
    if isinstance(value, dict):
        text = "; ".join(f"{key}: {_stringify(item, 60)}" for key, item in list(value.items())[:8])
    elif isinstance(value, (list, tuple)):
        text = ", ".join(_stringify(item, 40) for item in value[:8])
    else:
        text = str(value)
    return text[: max_chars - 1] + "\u2026" if len(text) > max_chars else text


def _flatten_metrics(
    metrics: dict[str, Any], prefix: str = ""
) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key, value in metrics.items():
        label = f"{prefix}{key}"
        if isinstance(value, dict):
            rows.extend(_flatten_metrics(value, prefix=f"{label} \u00b7 "))
        else:
            rows.append((label, value))
    return rows


class _WorkbookWriter:
    """Small helper wrapping xlsxwriter formatting primitives."""

    def __init__(self, workbook: Any) -> None:
        self.workbook = workbook
        base = {
            "font_name": "Calibri",
            "font_size": 10,
            "valign": "top",
        }
        self.formats = {
            "title": workbook.add_format({**base, "bold": True, "font_size": 16, "font_color": "#22303c"}),
            "subtitle": workbook.add_format({**base, "font_size": 10, "font_color": "#5b6770"}),
            "header": workbook.add_format(
                {
                    **base,
                    "bold": True,
                    "font_color": "#ffffff",
                    "bg_color": "#1f77b4",
                    "border": 1,
                    "border_color": "#9fb3c8",
                    "text_wrap": True,
                }
            ),
            "cell": workbook.add_format({**base, "border": 1, "border_color": "#d5dde4"}),
            "text": workbook.add_format({**base, "border": 1, "border_color": "#d5dde4"}),
            "number": workbook.add_format(
                {**base, "border": 1, "border_color": "#d5dde4", "num_format": "0.000"}
            ),
            "integer": workbook.add_format(
                {**base, "border": 1, "border_color": "#d5dde4", "num_format": "0"}
            ),
            "section": workbook.add_format({**base, "bold": True, "font_size": 11, "font_color": "#1f77b4"}),
            "note": workbook.add_format({**base, "italic": True, "font_color": "#5b6770", "text_wrap": True}),
        }

    def cell_format(self, value: Any) -> Any:
        if isinstance(value, bool):
            return self.formats["integer"]
        if isinstance(value, int):
            return self.formats["integer"]
        if isinstance(value, float):
            return self.formats["number"] if math.isfinite(value) else self.formats["cell"]
        return self.formats["text"]

    def write_cell(self, worksheet: Any, row: int, column: int, value: Any) -> None:
        converted = _excel_value(value)
        worksheet.write(row, column, converted, self.cell_format(converted))

    def write_frame(
        self,
        worksheet: Any,
        frame: pd.DataFrame,
        start_row: int = 0,
        *,
        max_rows: int | None = None,
        max_columns: int | None = None,
    ) -> int:
        """Write a DataFrame starting at ``start_row``; return the next free row."""
        if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
            worksheet.write(start_row, 0, "No rows available.", self.formats["note"])
            return start_row + 2
        working = frame
        if max_columns is not None and working.shape[1] > max_columns:
            working = working.iloc[:, :max_columns]
        if max_rows is not None and len(working) > max_rows:
            working = working.iloc[:max_rows]
        for column_index, column in enumerate(working.columns):
            worksheet.write(start_row, column_index, str(column), self.formats["header"])
        row = start_row + 1
        for _, record in working.iterrows():
            for column_index, column in enumerate(working.columns):
                self.write_cell(worksheet, row, column_index, record[column])
            row += 1
        worksheet.set_column(0, max(0, working.shape[1] - 1), 18)
        return row + 1

    def write_key_values(
        self, worksheet: Any, rows: Iterable[tuple[str, Any]], start_row: int = 0
    ) -> int:
        row = start_row
        for label, value in rows:
            worksheet.write(row, 0, label, self.formats["section"])
            self.write_cell(worksheet, row, 1, value)
            row += 1
        return row + 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_excel_report(
    results: Sequence[ExperimentResult],
    output_path: str | Path,
    *,
    config: Config | None = None,
    audit: DataAudit | None = None,
) -> Path:
    """Build a multi-sheet Excel workbook from experiment results.

    Parameters
    ----------
    results:
        Experiment results in presentation order.
    output_path:
        Destination ``.xlsx`` path; parent directories are created.
    config:
        Configuration providing report metadata.
    audit:
        Optional persisted :class:`~acousticbench.data.audit.DataAudit`.

    Returns
    -------
    Path
        The written workbook path.

    Raises
    ------
    ReportError
        If no results are supplied, xlsxwriter is unavailable, or writing
        fails.
    """
    cfg = config or load_config()
    sequence = list(results)
    if not sequence:
        raise ReportError("build_excel_report requires at least one experiment result")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        import xlsxwriter
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ReportError(
            "xlsxwriter is required for Excel reports but is not installed"
        ) from exc

    workbook = None
    try:
        workbook = xlsxwriter.Workbook(str(destination), {"nan_inf_to_errors": True})
        writer = _WorkbookWriter(workbook)
        used_names: set[str] = set()

        # -- Summary --------------------------------------------------------
        summary = workbook.add_worksheet(_sanitize_sheet_name("Summary", used_names))
        summary.set_column(0, 0, 28)
        summary.set_column(1, 6, 18)
        summary.write(0, 0, cfg.report.title, writer.formats["title"])
        summary.write(1, 0, cfg.project.description or cfg.dashboard.subtitle, writer.formats["subtitle"])
        summary.write(2, 0, f"Generated {datetime.now():%Y-%m-%d %H:%M:%S}", writer.formats["subtitle"])
        summary.write(
            3,
            0,
            f"{cfg.project.name} {cfg.project.version} \u00b7 {cfg.report.organisation}",
            writer.formats["subtitle"],
        )
        summary.write(4, 0, f"Experiments: {len(sequence)}", writer.formats["subtitle"])
        index_rows = [("Code", "Title", "Status", "Runtime [s]", "Tables", "Figures", "Warnings", "Error")]
        for result in sequence:
            index_rows.append(
                (
                    result.code,
                    result.title,
                    result.status,
                    round(float(result.duration_s), 2),
                    len(result.tables),
                    len(getattr(result, "figure_paths", {}) or {}),
                    len(result.warnings),
                    _stringify(result.error or "", 120),
                )
            )
        row = 6
        summary.write(row, 0, "Experiment index", writer.formats["section"])
        for offset, header in enumerate(index_rows[0]):
            summary.write(row + 1, offset, header, writer.formats["header"])
        for row_offset, record in enumerate(index_rows[1:], start=2):
            for column_offset, value in enumerate(record):
                writer.write_cell(summary, row + row_offset, column_offset, value)
        summary.freeze_panes(8, 0)
        summary.autofilter(row + 1, 0, row + 1 + len(index_rows) - 1, len(index_rows[0]) - 1)

        # -- Data Audit -----------------------------------------------------
        audit_sheet = workbook.add_worksheet(_sanitize_sheet_name("Data Audit", used_names))
        audit_sheet.set_column(0, 0, 34)
        audit_sheet.set_column(1, 5, 22)
        audit_sheet.write(0, 0, "Data quality audit", writer.formats["title"])
        if audit is None:
            audit_sheet.write(
                2,
                0,
                "No persisted data audit (results/audit/data_audit.json) was available when this "
                "workbook was generated.",
                writer.formats["note"],
            )
        else:
            n_passed = sum(1 for item in audit.findings if item.status == "PASS")
            row = writer.write_key_values(
                audit_sheet,
                [
                    ("Audit generated", audit.generated_at or _PLACEHOLDER),
                    ("Automated checks", len(audit.findings)),
                    ("Passed", n_passed),
                    ("Warnings", audit.n_warnings),
                    ("Errors", audit.n_errors),
                ],
                start_row=2,
            )
            file_info = (audit.dataset_summary or {}).get("file", {}) or {}
            row = writer.write_key_values(
                audit_sheet,
                [
                    ("Dataset", Path(str(file_info.get("path", "Data.mat"))).name),
                    ("Dataset size [MB]", round(float(file_info.get("size_mb", 0.0)), 1)),
                    ("MAT format", file_info.get("mat_format", _PLACEHOLDER)),
                    ("SHA-256", file_info.get("sha256", _PLACEHOLDER)),
                ],
                start_row=row,
            )
            audit_sheet.write(row, 0, "Automated checks", writer.formats["section"])
            row = writer.write_frame(audit_sheet, audit.checks_frame(), start_row=row + 1, max_rows=500)
            if audit.variables is not None and not audit.variables.empty:
                audit_sheet.write(row, 0, "Variables", writer.formats["section"])
                row = writer.write_frame(
                    audit_sheet, audit.variables, start_row=row + 1, max_rows=200
                )
            if audit.session_validity is not None and not audit.session_validity.empty:
                audit_sheet.write(row, 0, "Session validity", writer.formats["section"])
                row = writer.write_frame(
                    audit_sheet, audit.session_validity, start_row=row + 1, max_rows=200
                )
            if audit.invalid_sessions is not None and not audit.invalid_sessions.empty:
                audit_sheet.write(row, 0, "Invalid (NaN) sessions", writer.formats["section"])
                row = writer.write_frame(
                    audit_sheet, audit.invalid_sessions, start_row=row + 1, max_rows=500
                )
            if audit.structural_validity is not None and not audit.structural_validity.empty:
                audit_sheet.write(row, 0, "Structural validity rules", writer.formats["section"])
                writer.write_frame(
                    audit_sheet, audit.structural_validity, start_row=row + 1, max_rows=100
                )

        # -- Statistics -----------------------------------------------------
        statistics = workbook.add_worksheet(_sanitize_sheet_name("Statistics", used_names))
        headers = ["Experiment", "Metric", "Value", "Numeric"]
        for column_index, header in enumerate(headers):
            statistics.write(0, column_index, header, writer.formats["header"])
        statistics.set_column(0, 0, 12)
        statistics.set_column(1, 1, 52)
        statistics.set_column(2, 2, 24)
        statistics.set_column(3, 3, 14)
        row = 1
        for result in sequence:
            for label, value in _flatten_metrics(result.metrics):
                statistics.write(row, 0, result.code, writer.formats["text"])
                statistics.write(row, 1, label, writer.formats["text"])
                statistics.write(row, 2, _stringify(value), writer.formats["text"])
                if isinstance(value, (int, float, bool)) and not isinstance(value, bool):
                    writer.write_cell(statistics, row, 3, float(value))
                else:
                    statistics.write(row, 3, "", writer.formats["text"])
                row += 1
        statistics.freeze_panes(1, 0)
        if row > 1:
            statistics.autofilter(0, 0, row - 1, 3)

        # -- one sheet per experiment table (row-capped for file size) ------
        seen_table_digests: set[str] = set()
        for result in sequence:
            for table_name, frame in result.tables.items():
                if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
                    continue  # never create empty sheets
                digest = _frame_digest(frame)
                if digest in seen_table_digests:
                    continue  # never duplicate an identical table sheet
                seen_table_digests.add(digest)
                sheet_name = _sanitize_sheet_name(f"{result.code} {table_name}", used_names)
                worksheet = workbook.add_worksheet(sheet_name)
                worksheet.write(0, 0, f"{result.code} \u2014 {result.title}", writer.formats["title"])
                worksheet.write(1, 0, f"Table: {table_name}", writer.formats["subtitle"])
                total_rows = int(len(frame))
                if total_rows > _MAX_SHEET_ROWS:
                    hint = _full_table_hint(result, table_name)
                    worksheet.write(
                        3,
                        0,
                        f"(first {_MAX_SHEET_ROWS} of {total_rows} rows; full table in {hint})",
                        writer.formats["note"],
                    )
                else:
                    worksheet.write(
                        3, 0, f"(all {total_rows} rows of this table are shown)", writer.formats["note"]
                    )
                writer.write_frame(
                    worksheet, frame, start_row=5, max_rows=_MAX_SHEET_ROWS
                )
                worksheet.freeze_panes(6, 0)
    except ReportError:
        raise
    except Exception as exc:  # noqa: BLE001 - wrap xlsxwriter failures with context
        raise ReportError(f"Excel report generation failed: {exc}") from exc
    finally:
        if workbook is not None:
            try:
                workbook.close()
            except Exception:  # pragma: no cover - close must not mask the real error
                pass

    if not destination.is_file() or destination.stat().st_size == 0:
        raise ReportError(f"Excel report was not written: {destination}")
    return destination
