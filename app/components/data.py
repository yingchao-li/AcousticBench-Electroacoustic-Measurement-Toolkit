"""Cached data access for the dashboard.

Everything expensive is cached with ``st.cache_resource`` and invalidated by
file metadata (path, size, modification time) or by a compact signature of the
persisted artefacts, so a regenerated experiment or a replaced ``Data.mat`` is
picked up without restarting the server.  Every loader returns a small state
object with an explicit ``error`` field instead of raising, so pages can render
an actionable message and never crash.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import streamlit as st

from acousticbench.config import Config, load_config
from acousticbench.data.audit import DataAudit
from acousticbench.data.dataset import AcousticDataset, load_dataset
from acousticbench.report.builder import (
    SavedExperimentResult,
    load_saved_audit,
    load_saved_results,
)

__all__ = [
    "AuditState",
    "DatasetState",
    "ResultsState",
    "get_audit_state",
    "get_config",
    "get_dataset_state",
    "get_index_state",
    "get_results_state",
    "get_saved_audit_for_report",
    "has_optional_module",
    "optional_module",
    "result_for",
    "run_audit_now",
]


@dataclass
class DatasetState:
    """Outcome of loading the measurement dataset."""

    dataset: AcousticDataset | None = None
    error: str | None = None
    path: str = ""
    size_mb: float = 0.0

    @property
    def ok(self) -> bool:
        return self.dataset is not None and self.error is None


@dataclass
class AuditState:
    """Outcome of loading (or running) the data-quality audit."""

    audit: DataAudit | None = None
    source: str = "unavailable"  # persisted | computed | unavailable
    error: str | None = None


@dataclass
class ResultsState:
    """Persisted experiment results and the saved experiment index."""

    results: list[SavedExperimentResult] = field(default_factory=list)
    index: dict[str, Any] | None = None
    error: str | None = None

    @property
    def by_code(self) -> dict[str, SavedExperimentResult]:
        return {result.code: result for result in self.results}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_config() -> Config:
    """Load and cache the typed configuration."""
    return load_config()


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading the measurement dataset (Data.mat) ...")
def _load_dataset_cached(path: str, mtime_ns: int, size_bytes: int) -> DatasetState:
    _ = (mtime_ns, size_bytes)  # part of the cache key only
    try:
        dataset = load_dataset(path, config=get_config(), compute_hash=True)
    except Exception as exc:  # noqa: BLE001 - the UI renders the message
        return DatasetState(
            dataset=None,
            error=f"{type(exc).__name__}: {exc}",
            path=path,
            size_mb=size_bytes / 1024**2,
        )
    return DatasetState(
        dataset=dataset,
        error=None,
        path=path,
        size_mb=size_bytes / 1024**2,
    )


def get_dataset_state() -> DatasetState:
    """Return the cached dataset state (never raises)."""
    path = get_config().data_path
    if not path.is_file():
        return DatasetState(
            dataset=None,
            error=f"Data file not found at {path}.",
            path=str(path),
        )
    try:
        stat = path.stat()
    except OSError as exc:
        return DatasetState(dataset=None, error=str(exc), path=str(path))
    return _load_dataset_cached(str(path), stat.st_mtime_ns, stat.st_size)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _load_saved_audit_cached(audit_json_mtime_ns: int, results_dir: str) -> AuditState:
    _ = audit_json_mtime_ns
    audit = load_saved_audit(results_dir)
    if audit is None:
        return AuditState(audit=None, source="unavailable", error="No readable persisted audit.")
    return AuditState(audit=audit, source="persisted", error=None)


def get_audit_state() -> AuditState:
    """Load the persisted audit from ``results/audit`` (never raises)."""
    json_path = get_config().results_dir / "audit" / "data_audit.json"
    if not json_path.is_file():
        return AuditState(
            audit=None,
            source="unavailable",
            error=(
                "No persisted audit was found at "
                f"{json_path}. Run the data audit to generate it."
            ),
        )
    try:
        mtime = json_path.stat().st_mtime_ns
    except OSError as exc:
        return AuditState(audit=None, source="unavailable", error=str(exc))
    return _load_saved_audit_cached(mtime, str(get_config().results_dir))


@st.cache_resource(show_spinner="Running the full data-quality audit ...")
def _run_audit_cached(data_path: str, data_mtime_ns: int) -> AuditState:
    _ = (data_path, data_mtime_ns)
    state = get_dataset_state()
    if state.dataset is None:
        return AuditState(audit=None, source="unavailable", error=state.error)
    try:
        audit = state.dataset.audit()
    except Exception as exc:  # noqa: BLE001 - the UI renders the message
        return AuditState(
            audit=None, source="unavailable", error=f"{type(exc).__name__}: {exc}"
        )
    return AuditState(audit=audit, source="computed", error=None)


def run_audit_now() -> AuditState:
    """Compute the audit in memory (not persisted)."""
    path = get_config().data_path
    try:
        stat = path.stat()
    except OSError:
        return AuditState(audit=None, source="unavailable", error=f"Data file not found at {path}")
    return _run_audit_cached(str(path), stat.st_mtime_ns)


def get_saved_audit_for_report() -> DataAudit | None:
    """Return the audit used by the report builders (persisted artefact only)."""
    return load_saved_audit(get_config().results_dir)


# ---------------------------------------------------------------------------
# Persisted experiment results
# ---------------------------------------------------------------------------
def _experiments_signature(experiments_root: Path) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    if experiments_root.is_dir():
        for result_file in sorted(experiments_root.glob("*/result.json")):
            try:
                entries.append((result_file.parent.name, result_file.stat().st_mtime_ns))
            except OSError:
                continue
    return tuple(entries)


def _index_signature(index_file: Path) -> int:
    try:
        return index_file.stat().st_mtime_ns
    except OSError:
        return 0


@st.cache_resource(show_spinner=False)
def _load_results_cached(
    signature: tuple[tuple[str, int], ...],
    results_dir: str,
    index_mtime_ns: int,
    index_path: str,
) -> ResultsState:
    _ = (signature, index_mtime_ns)
    try:
        results = load_saved_results(results_dir, get_config())
    except Exception as exc:  # noqa: BLE001 - the UI renders the message
        return ResultsState(results=[], index=None, error=f"{type(exc).__name__}: {exc}")
    index: dict[str, Any] | None = None
    index_file = Path(index_path)
    if index_file.is_file():
        try:
            index = json.loads(index_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ResultsState(
                results=results, index=None, error=f"Experiment index unreadable: {exc}"
            )
    return ResultsState(results=results, index=index, error=None)


def get_results_state() -> ResultsState:
    """Return all persisted experiment results (cached by artefact signature)."""
    results_dir = get_config().results_dir
    experiments_root = results_dir / "experiments"
    index_file = experiments_root / "experiment_index.json"
    return _load_results_cached(
        _experiments_signature(experiments_root),
        str(results_dir),
        _index_signature(index_file),
        str(index_file),
    )


def result_for(code: str) -> SavedExperimentResult | None:
    """Return one persisted result by experiment code, or ``None``."""
    return get_results_state().by_code.get(str(code).upper())


def get_index_state() -> tuple[dict[str, Any] | None, str | None]:
    """Return the persisted experiment index and an error message if unreadable."""
    state = get_results_state()
    if state.index is None:
        return None, state.error or "results/experiments/experiment_index.json not found"
    return state.index, state.error


# ---------------------------------------------------------------------------
# Optional modules (DSP / virtual HA / synthetic / validation)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def optional_module(module_name: str) -> tuple[Any | None, str | None]:
    """Import an optional module, returning ``(module, error)`` without raising."""
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - optional integration
        return None, f"{type(exc).__name__}: {exc}"
    return module, None


def has_optional_module(module_name: str) -> bool:
    """Return ``True`` when ``module_name`` imports successfully."""
    module, _ = optional_module(module_name)
    return module is not None
