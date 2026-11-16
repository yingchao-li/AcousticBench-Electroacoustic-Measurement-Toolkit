"""Plotting and report generation.

Public builders
---------------
``build_pdf_report``, ``build_excel_report``, ``build_html_report``
    Format-specific builders operating on ``ExperimentResult`` sequences.
``build_all_reports``, ``generate``
    Orchestration with timestamped file names under ``reports/``.
``load_saved_results``, ``load_saved_audit``
    Reconstruct persisted results/audit artefacts for reporting.

The plotting helpers remain importable as ``from acousticbench.report import figures``
and are shared with the experiments and the dashboard.
"""

from acousticbench.report import figures
from acousticbench.report.builder import (
    SUPPORTED_FORMATS,
    SavedExperimentResult,
    build_all_reports,
    generate,
    load_saved_audit,
    load_saved_results,
    report_metadata,
)
from acousticbench.report.excel import build_excel_report
from acousticbench.report.html import build_html_report
from acousticbench.report.pdf import build_pdf_report

__all__ = [
    "SUPPORTED_FORMATS",
    "SavedExperimentResult",
    "build_all_reports",
    "build_excel_report",
    "build_html_report",
    "build_pdf_report",
    "figures",
    "generate",
    "load_saved_audit",
    "load_saved_results",
    "report_metadata",
]
