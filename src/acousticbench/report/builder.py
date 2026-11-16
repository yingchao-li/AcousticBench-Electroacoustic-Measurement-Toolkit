"""Report orchestration and reconstruction of saved experiment results.

The report builders (:mod:`acousticbench.report.pdf`, ``excel`` and ``html``)
consume :class:`~acousticbench.experiments.base.ExperimentResult` objects.  An
experiment run persists its artefacts on disk as::

    results/experiments/E01_frequency_response/
        result.json          # ExperimentResult.to_dict() (no figures)
        summary.md
        tables/<name>.csv      # small tables
        tables/<name>.csv.gz   # large tables (compressed)
        figures/*.png

:func:`load_saved_results` reads that layout back into
:class:`SavedExperimentResult`, a small subclass of ``ExperimentResult`` that
additionally carries the resolved artefact paths.  The subclass keeps the
public ``ExperimentResult`` contract (code/title/status/metrics/tables/
narrative/...) so every builder can consume saved and freshly-run results
alike; only figure rendering differs (saved results expose ``figure_paths``
instead of live matplotlib figures).

The module is deliberately free of dashboard/Streamlit imports so that it can
also be used by the CLI.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

from acousticbench.config import Config, load_config
from acousticbench.data.audit import AuditFinding, DataAudit
from acousticbench.exceptions import ReportError
from acousticbench.experiments.base import ExperimentResult

__all__ = [
    "SUPPORTED_FORMATS",
    "SavedExperimentResult",
    "build_all_reports",
    "generate",
    "load_saved_audit",
    "load_saved_results",
    "report_filename",
]

#: Report formats supported by :func:`build_all_reports` and :func:`generate`.
SUPPORTED_FORMATS: tuple[str, ...] = ("pdf", "excel", "html")

#: Extension of each supported format.
FORMAT_EXTENSIONS: dict[str, str] = {"pdf": "pdf", "excel": "xlsx", "html": "html"}

_EXPERIMENT_DIR_RE = re.compile(r"^[A-Z]\d{2}_")


@dataclass
class SavedExperimentResult(ExperimentResult):
    """An ``ExperimentResult`` reconstructed from disk artefacts.

    Parameters
    ----------
    directory:
        Experiment directory (``results/experiments/E01_...``).
    figure_paths:
        Mapping ``figure name -> PNG path`` read from ``figures/``.
    table_paths:
        Mapping ``table name -> CSV path`` read from ``tables/``.

    Notes
    -----
    ``tables`` is populated with the CSV contents (full frames, exactly as
    persisted).  ``figures`` stays empty because the figures are image files,
    not live matplotlib objects; use :attr:`figure_paths` to embed them.
    """

    directory: Path | None = None
    figure_paths: dict[str, Path] = field(default_factory=dict)
    table_paths: dict[str, Path] = field(default_factory=dict)

    def figure_items(self) -> list[tuple[str, Path]]:
        """Return ``(name, path)`` pairs of existing figure files."""
        return [(name, path) for name, path in sorted(self.figure_paths.items()) if path.is_file()]


# ---------------------------------------------------------------------------
# Loading saved artefacts
# ---------------------------------------------------------------------------
def _experiments_root(results_root: str | Path) -> Path:
    root = Path(results_root)
    nested = root / "experiments"
    return nested if nested.is_dir() else root


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_")
    return cleaned or "table"


def load_saved_results(
    results_root: str | Path,
    config: Config | None = None,
) -> list[SavedExperimentResult]:
    """Read every saved experiment under ``results/experiments``.

    Parameters
    ----------
    results_root:
        ``results`` directory (or the ``experiments`` sub-directory directly).
    config:
        Optional configuration (kept for API symmetry; defaults to
        :func:`acousticbench.config.load_config`).

    Returns
    -------
    list[SavedExperimentResult]
        Sorted by experiment code.  Directories without a readable
        ``result.json`` are skipped; malformed CSV tables are skipped with the
        table left out rather than aborting the whole load.
    """
    _ = config or load_config()
    root = _experiments_root(results_root)
    if not root.is_dir():
        return []

    results: list[SavedExperimentResult] = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or not _EXPERIMENT_DIR_RE.match(directory.name):
            continue
        result_file = directory / "result.json"
        if not result_file.is_file():
            continue
        try:
            payload = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        table_paths: dict[str, Path] = {}
        tables: dict[str, pd.DataFrame] = {}
        tables_dir = directory / "tables"
        if tables_dir.is_dir():
            # Large tables are persisted as ``<name>.csv.gz``; small tables stay
            # ``<name>.csv``.  Both may exist transiently after a runner change,
            # in which case the compressed (current, full-resolution) file wins.
            candidates: dict[str, list[tuple[int, Path]]] = {}
            for table_file in sorted(tables_dir.iterdir()):
                if not table_file.is_file():
                    continue
                if table_file.name.endswith(".csv.gz"):
                    base_name, preference = table_file.name[:-7], 1
                elif table_file.name.endswith(".csv"):
                    base_name, preference = table_file.name[:-4], 0
                else:
                    continue
                candidates.setdefault(base_name, []).append((preference, table_file))
            for base_name, files in sorted(candidates.items()):
                files.sort(key=lambda item: item[0], reverse=True)
                for _, table_file in files:
                    try:
                        tables[base_name] = pd.read_csv(table_file)
                    except (OSError, pd.errors.ParserError, ValueError):
                        continue
                    table_paths[base_name] = table_file
                    break

        figure_paths: dict[str, Path] = {}
        figures_dir = directory / "figures"
        if figures_dir.is_dir():
            for image_path in sorted(figures_dir.iterdir()):
                if image_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".svg"}:
                    figure_paths[image_path.stem] = image_path

        narrative = str(payload.get("narrative") or "")
        if not narrative:
            summary_file = directory / "summary.md"
            if summary_file.is_file():
                try:
                    narrative = summary_file.read_text(encoding="utf-8")
                except OSError:
                    narrative = ""

        results.append(
            SavedExperimentResult(
                code=str(payload.get("code") or directory.name.split("_", 1)[0]),
                title=str(payload.get("title") or directory.name.split("_", 1)[-1].replace("_", " ")),
                status=str(payload.get("status") or "completed"),
                metrics=dict(payload.get("metrics") or {}),
                tables=tables,
                figures={},
                warnings=[str(item) for item in payload.get("warnings") or []],
                narrative=narrative,
                duration_s=float(payload.get("duration_s") or 0.0),
                parameters=dict(payload.get("parameters") or {}),
                data_provenance=dict(payload.get("data_provenance") or {}),
                error=payload.get("error"),
                artifacts=dict(payload.get("artifacts") or {}),
                directory=directory,
                figure_paths=figure_paths,
                table_paths=table_paths,
            )
        )
    # A re-run can briefly leave an old and a new directory for the same code
    # (for example after the runner changed its directory slug).  Keep the
    # newest artefact set per experiment code so reports never duplicate a
    # section or mix stale tables with fresh ones.
    latest_by_code: dict[str, SavedExperimentResult] = {}
    for item in results:
        previous = latest_by_code.get(item.code)
        if previous is None or _artefact_mtime(item) > _artefact_mtime(previous):
            latest_by_code[item.code] = item
    return sorted(latest_by_code.values(), key=lambda item: item.code)


def _artefact_mtime(result: SavedExperimentResult) -> int:
    """Modification time of the experiment's result.json (0 when missing)."""
    if result.directory is None:
        return 0
    try:
        return (result.directory / "result.json").stat().st_mtime_ns
    except OSError:
        return 0


def load_saved_audit(results_root: str | Path) -> DataAudit | None:
    """Reconstruct the persisted :class:`DataAudit` from ``results/audit``.

    The audit is always loaded from disk (never recomputed here) so that
    reports generated later describe exactly the audit that was accepted.

    Parameters
    ----------
    results_root:
        ``results`` directory or the ``audit`` directory itself.

    Returns
    -------
    DataAudit | None
        ``None`` when no ``data_audit.json`` exists or it cannot be parsed.
    """
    root = Path(results_root)
    audit_path = root if root.name == "audit" else root / "audit"
    json_path = audit_path / "data_audit.json"
    if not json_path.is_file():
        return None
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    def frame(key: str) -> pd.DataFrame:
        rows = payload.get(key) or []
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    findings: list[AuditFinding] = []
    for row in payload.get("checks") or []:
        status = str(row.get("status", "INFO")).upper()
        passed = None if status == "INFO" else status == "PASS"
        severity = str(row.get("severity") or ("info" if passed is None else ("warning" if passed is False else "info")))
        findings.append(
            AuditFinding(
                severity=severity,
                code=str(row.get("code", "")),
                message=str(row.get("message", "")),
                expected=row.get("expected"),
                observed=row.get("observed"),
                passed=passed,
            )
        )
    return DataAudit(
        dataset_summary=dict(payload.get("dataset") or {}),
        variables=frame("variables"),
        session_validity=frame("session_validity"),
        invalid_sessions=frame("invalid_sessions"),
        structural_validity=frame("structural_validity"),
        findings=findings,
        derived=dict(payload.get("derived") or {}),
        frequency_axis=dict(payload.get("frequency_axis") or {}),
        threshold_axis=dict(payload.get("threshold_axis") or {}),
        provenance=dict(payload.get("provenance") or {}),
        generated_at=str(payload.get("generated_at") or ""),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def report_filename(timestamp: datetime | None = None) -> str:
    """Return the shared timestamped report base name (without extension)."""
    stamp = timestamp or datetime.now()
    return f"AcousticBench_Report_{stamp.strftime('%Y%m%d_%H%M%S')}"


def _validate_formats(formats: Iterable[str]) -> tuple[str, ...]:
    normalised = tuple(str(item).strip().lower() for item in formats)
    unknown = [item for item in normalised if item not in SUPPORTED_FORMATS]
    if unknown:
        raise ReportError(
            f"Unknown report format(s) {unknown}; supported: {list(SUPPORTED_FORMATS)}"
        )
    if not normalised:
        raise ReportError("At least one report format is required")
    return normalised


def build_all_reports(
    results: Sequence[ExperimentResult],
    output_dir: str | Path,
    *,
    config: Config | None = None,
    audit: DataAudit | None = None,
    formats: Iterable[str] = ("pdf", "excel", "html"),
) -> dict[str, Path]:
    """Build the requested report formats from experiment results.

    Parameters
    ----------
    results:
        Experiment results (freshly run or reconstructed by
        :func:`load_saved_results`).
    output_dir:
        Destination directory; created when missing.
    config:
        Report configuration.  Defaults to :func:`load_config`.
    audit:
        Optional data audit included in every format.
    formats:
        Any subset of ``("pdf", "excel", "html")``.

    Returns
    -------
    dict[str, Path]
        Mapping ``format -> generated path``.  File names share one timestamp,
        e.g. ``AcousticBench_Report_20260422_101500.pdf``.

    Raises
    ------
    ReportError
        If no results are supplied, a format is unknown, or a builder fails.
    """
    from acousticbench.report import excel, html, pdf

    cfg = config or load_config()
    selected = _validate_formats(formats)
    sequence = list(results)
    if not sequence:
        raise ReportError(
            "No experiment results available; run experiments before generating a report"
        )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = report_filename()
    paths: dict[str, Path] = {}

    if "pdf" in selected:
        paths["pdf"] = pdf.build_pdf_report(
            sequence, out / f"{base}.pdf", config=cfg, audit=audit
        )
    if "excel" in selected:
        paths["excel"] = excel.build_excel_report(
            sequence, out / f"{base}.xlsx", config=cfg, audit=audit
        )
    if "html" in selected:
        paths["html"] = html.build_html_report(
            sequence, out / f"{base}.html", config=cfg, audit=audit
        )
    return paths


def generate(
    *,
    config: Config | None = None,
    results: Sequence[ExperimentResult] | None = None,
    audit: DataAudit | None = None,
    output_dir: str | Path | None = None,
    formats: Iterable[str] = ("pdf", "excel", "html"),
) -> dict[str, Path]:
    """Convenience wrapper used by the Report Center (and the future CLI).

    Missing results/audit are loaded from the persisted artefacts; when no
    saved experiment exists a :class:`~acousticbench.exceptions.ReportError`
    is raised with an actionable message.
    """
    cfg = config or load_config()
    selected_results = (
        list(results) if results else load_saved_results(cfg.results_dir, cfg)
    )
    selected_audit = audit if audit is not None else load_saved_audit(cfg.results_dir)
    destination = Path(output_dir) if output_dir is not None else cfg.reports_dir
    paths = build_all_reports(
        selected_results,
        destination,
        config=cfg,
        audit=selected_audit,
        formats=formats,
    )
    return paths


def report_metadata(paths: dict[str, Path]) -> dict[str, Any]:
    """Small metadata dict (format, path, bytes, modified time) for the UI."""
    metadata: dict[str, Any] = {}
    for fmt, path in paths.items():
        try:
            stat = path.stat()
        except OSError:
            continue
        metadata[fmt] = {
            "path": str(path),
            "name": path.name,
            "size_bytes": int(stat.st_size),
            "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        }
    return metadata
