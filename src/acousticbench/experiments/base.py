"""Shared infrastructure for experiments E01–E16.

An experiment is a module exposing:

``CODE``, ``TITLE``, ``DESCRIPTION``
    Metadata strings.
``run(context) -> ExperimentResult``
    Pure analysis function.  It must not write files; it returns tables,
    matplotlib figures, metrics and a Markdown narrative.  The runner persists
    everything in a deterministic directory layout.

This separation keeps experiments testable (no I/O side effects) and makes the
artefacts reproducible from the saved configuration and data provenance.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acousticbench.config import Config
from acousticbench.data.audit import DataAudit
from acousticbench.data.dataset import AcousticDataset, TransferCube
from acousticbench.exceptions import ExperimentError
from acousticbench.logging_utils import get_logger

__all__ = [
    "Experiment",
    "ExperimentContext",
    "ExperimentResult",
    "ExperimentRunner",
    "ExperimentSpec",
]


@dataclass
class ExperimentContext:
    """Runtime context handed to an experiment."""

    code: str
    dataset: AcousticDataset
    config: Config
    seed: int
    logger: logging.Logger = field(default_factory=lambda: get_logger("experiments"))
    parameters: dict[str, Any] = field(default_factory=dict)
    audit: DataAudit | None = None

    @property
    def rng(self) -> np.random.Generator:
        return np.random.default_rng(self.seed)

    def params(self, code: str | None = None) -> dict[str, Any]:
        """Experiment parameters merged with the global analysis defaults."""
        requested = code or self.code
        merged = dict(self.config.experiment_params(requested))
        return merged

    def data_provenance(self) -> dict[str, Any]:
        info = self.dataset.info
        return {
            "dataset_path": info.path.name,
            "sha256": info.sha256,
            "mat_format": info.mat_format,
            "n_frequencies": int(self.dataset.frequency_hz.size),
            "n_subjects": int(self.dataset.subjects.size),
            "n_reinsertions": int(self.dataset.reinsertions.size),
            "n_devices": len(self.dataset.devices),
            "invalid_policy": self.config.data.invalid_policy,
        }

    def bands(self):  # noqa: ANN201 - returns tuple[Band, ...]
        from acousticbench.stats.bands import bands_from_config

        return bands_from_config(self.config)


class Experiment(Protocol):
    """Structural protocol implemented by experiment modules."""

    CODE: str
    TITLE: str
    DESCRIPTION: str

    def run(self, context: ExperimentContext) -> "ExperimentResult":  # pragma: no cover
        ...


@dataclass
class ExperimentResult:
    """Outcome of one experiment, including all reproducible artefacts."""

    code: str
    title: str
    status: str = "completed"  # completed | failed | skipped
    metrics: dict[str, Any] = field(default_factory=dict)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    figures: dict[str, plt.Figure] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    narrative: str = ""
    duration_s: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)
    data_provenance: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    artifacts: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable summary (without figure objects)."""
        return {
            "code": self.code,
            "title": self.title,
            "status": self.status,
            "metrics": _jsonable(self.metrics),
            "tables": {
                name: {
                    "rows": int(len(frame)),
                    "columns": list(frame.columns.astype(str)),
                }
                for name, frame in self.tables.items()
            },
            "figures": list(self.figures),
            "artifacts": dict(self.artifacts),
            "warnings": list(self.warnings),
            "narrative": self.narrative,
            "duration_s": round(self.duration_s, 3),
            "parameters": _jsonable(self.parameters),
            "data_provenance": _jsonable(self.data_provenance),
            "error": self.error,
        }


@dataclass(frozen=True)
class ExperimentSpec:
    """Registry entry for an experiment."""

    code: str
    title: str
    description: str
    runner: Callable[[ExperimentContext], ExperimentResult]
    module: str = ""


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        out = float(value)
        return None if not np.isfinite(out) else out
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, Path):
        return str(value)
    return value


class ExperimentRunner:
    """Execute experiments and persist their artefacts."""

    def __init__(
        self,
        config: Config,
        *,
        output_root: str | Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or get_logger("experiments.runner")
        self.output_root = Path(output_root) if output_root else config.results_dir / "experiments"
        self.output_root.mkdir(parents=True, exist_ok=True)

    # -- discovery ----------------------------------------------------------
    @staticmethod
    def specs() -> dict[str, ExperimentSpec]:
        from acousticbench.experiments.registry import EXPERIMENTS

        return dict(EXPERIMENTS)

    def resolve_codes(self, codes: Sequence[str] | str | None = None) -> list[str]:
        specs = self.specs()
        if codes is None:
            selected = list(self.config.experiments.enabled)
            selected = [code for code in selected if code in specs]
        elif isinstance(codes, str):
            selected = [codes]
        else:
            selected = list(codes)
        unknown = [code for code in selected if code not in specs]
        if unknown:
            raise ExperimentError(
                f"Unknown experiment code(s): {unknown}; available: {sorted(specs)}"
            )
        return selected

    # -- execution ----------------------------------------------------------
    def run(
        self,
        code: str,
        *,
        dataset: AcousticDataset | None = None,
        audit: DataAudit | None = None,
        save: bool = True,
    ) -> ExperimentResult:
        specs = self.specs()
        if code not in specs:
            raise ExperimentError(f"Unknown experiment {code!r}")
        spec = specs[code]
        ds = dataset or AcousticDataset.from_file(config=self.config)
        parameters = {"code": code, **dict(self.config.experiment_params(code))}
        context = ExperimentContext(
            code=code,
            dataset=ds,
            config=self.config,
            seed=int(self.config.project.seed),
            logger=get_logger(f"experiments.{code}"),
            parameters=parameters,
            audit=audit,
        )
        started = time.perf_counter()
        self.logger.info("Starting %s – %s", code, spec.title)
        try:
            result = spec.runner(context)
        except Exception as exc:  # noqa: BLE001 - record failure, re-raise only if strict
            duration = time.perf_counter() - started
            self.logger.exception("Experiment %s failed", code)
            result = ExperimentResult(
                code=code,
                title=spec.title,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                duration_s=duration,
                parameters=_jsonable(parameters),
                data_provenance=_jsonable(context.data_provenance()),
            )
        else:
            result.duration_s = time.perf_counter() - started
            result.parameters = _jsonable(parameters)
            result.data_provenance = _jsonable(context.data_provenance())
        result.code = result.code or code
        result.title = result.title or spec.title
        self.logger.info(
            "Finished %s in %.2f s with status=%s (%d tables, %d figures)",
            code,
            result.duration_s,
            result.status,
            len(result.tables),
            len(result.figures),
        )
        if save:
            self.save(result, spec, ds)
        return result

    def run_all(
        self,
        codes: Sequence[str] | None = None,
        *,
        dataset: AcousticDataset | None = None,
        audit: DataAudit | None = None,
    ) -> list[ExperimentResult]:
        ds = dataset or AcousticDataset.from_file(config=self.config)
        results = []
        for code in self.resolve_codes(codes):
            results.append(self.run(code, dataset=ds, audit=audit, save=True))
        self.write_index(results)
        return results

    # -- artefact persistence ----------------------------------------------
    def _directory(self, result: ExperimentResult) -> Path:
        slug = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in result.title.lower().replace(" ", "_")
        ).strip("_")
        return self.output_root / f"{result.code}_{slug}"

    def save(
        self,
        result: ExperimentResult,
        spec: ExperimentSpec,
        dataset: AcousticDataset,
    ) -> Path:
        directory = self._directory(result)
        tables_dir = directory / "tables"
        figures_dir = directory / "figures"
        # Remove stale artefacts from previous runs so that table formats or
        # figure sets cannot silently mix between runs.
        for stale in (tables_dir, figures_dir):
            if stale.exists():
                shutil.rmtree(stale)
        tables_dir.mkdir(parents=True, exist_ok=True)
        figures_dir.mkdir(parents=True, exist_ok=True)

        saved_tables: list[str] = []
        for name, frame in result.tables.items():
            base = _safe_name(name)
            # Full-resolution tables can be large; store them gzip-compressed so
            # that the committed artefacts remain reviewable.  The report loader
            # understands both .csv and .csv.gz.
            if len(frame) > 2000:
                path = tables_dir / f"{base}.csv.gz"
                frame.to_csv(
                    path, index=False, compression="gzip", float_format="%.12g"
                )
            else:
                path = tables_dir / f"{base}.csv"
                frame.to_csv(path, index=False, float_format="%.12g")
            saved_tables.append(path.name)

        saved_figures: list[str] = []
        for name, figure in result.figures.items():
            path = figures_dir / f"{_safe_name(name)}.{self.config.experiments.figure_format}"
            try:
                figure.savefig(path, dpi=self.config.experiments.figure_dpi, bbox_inches="tight")
            finally:
                plt.close(figure)
            saved_figures.append(path.name)
        result.figures = {}

        result.artifacts = {"tables": saved_tables, "figures": saved_figures}

        # result.json
        (directory / "result.json").write_text(
            json.dumps(result.to_dict(), indent=2, allow_nan=False), encoding="utf-8"
        )
        # summary.md
        (directory / "summary.md").write_text(self.markdown(result), encoding="utf-8")
        # config snapshot
        if self.config.experiments.save_config_snapshot:
            (directory / "config_snapshot.json").write_text(
                json.dumps(
                    {
                        "project_seed": self.config.project.seed,
                        "analysis": {
                            "alpha": self.config.analysis.alpha,
                            "correction": self.config.analysis.correction,
                            "bootstrap": dataclasses.asdict(self.config.analysis.bootstrap),
                            "bands": dataclasses.asdict(self.config.analysis.bands),
                        },
                        "experiment_parameters": result.parameters,
                        "figures": {
                            "format": self.config.experiments.figure_format,
                            "dpi": self.config.experiments.figure_dpi,
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        return directory

    def markdown(self, result: ExperimentResult) -> str:
        lines = [
            f"# {result.code} — {result.title}",
            "",
            f"**Status:** `{result.status}`  ",
            f"**Runtime:** {result.duration_s:.2f} s  ",
            f"**Seed:** {self.config.project.seed}",
            "",
        ]
        if result.error:
            lines.extend(["## Error", "", "```", result.error, "```", ""])
        lines.extend(["## Metrics", ""])
        if result.metrics:
            lines.extend(["| metric | value |", "| --- | --- |"])
            for key, value in result.metrics.items():
                if isinstance(value, (dict, list)):
                    continue
                lines.append(f"| `{key}` | {value} |")
            lines.append("")
        if result.narrative:
            lines.extend(["## Summary", "", result.narrative, ""])
        if result.warnings:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in result.warnings)
            lines.append("")
        if result.tables:
            lines.extend(["## Tables", ""])
            for name, frame in result.tables.items():
                lines.append(f"### `{name}` ({len(frame)} rows)")
                lines.append("")
                preview = frame.head(12)
                lines.append(preview.to_markdown(index=False))
                lines.append("")
        if result.artifacts:
            lines.extend(["## Artefacts", ""])
            for kind, files in result.artifacts.items():
                lines.append(f"- {kind}: " + ", ".join(f"`{f}`" for f in files))
            lines.append("")
        lines.extend(
            [
                "## Data provenance",
                "",
                "```json",
                json.dumps(result.data_provenance, indent=2),
                "```",
                "",
            ]
        )
        return "\n".join(lines)

    def write_index(self, results: Sequence[ExperimentResult]) -> Path:
        """Merge the current results into the experiment index.

        Running a subset of experiments must not discard the entries of
        previously executed experiments (the dashboard and reports rely on the
        complete index).
        """
        index_path = self.output_root / "experiment_index.json"
        merged: dict[str, dict[str, Any]] = {}
        if index_path.is_file():
            try:
                previous = json.loads(index_path.read_text(encoding="utf-8"))
                for entry in previous.get("experiments", []):
                    code = str(entry.get("code") or "")
                    if code:
                        merged[code] = entry
            except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive
                merged = {}
        for result in results:
            merged[result.code] = result.to_dict()
        ordered = [merged[code] for code in sorted(merged)]
        payload = {
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "project": self.config.project.name,
            "version": self.config.project.version,
            "experiments": ordered,
        }
        index_path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
        summary = pd.DataFrame(
            [
                {
                    "code": entry.get("code"),
                    "title": entry.get("title"),
                    "status": entry.get("status"),
                    "duration_s": entry.get("duration_s"),
                    "n_tables": len((entry.get("artifacts") or {}).get("tables", [])),
                    "n_figures": len((entry.get("artifacts") or {}).get("figures", [])),
                    "warnings": len(entry.get("warnings") or []),
                    "error": entry.get("error") or "",
                    "directory": "",
                }
                for entry in ordered
            ]
        )
        # Recover the directory names from the saved artefacts.
        for index, entry in enumerate(ordered):
            code = str(entry.get("code"))
            candidates = sorted(self.output_root.glob(f"{code}_*"))
            if candidates:
                summary.loc[index, "directory"] = candidates[-1].name
        summary.to_csv(self.output_root / "experiment_index.csv", index=False)
        return index_path


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in name).strip("_")


def experiment_table_frame(cube: TransferCube) -> pd.DataFrame:
    """Convenience: tidy level frame from a cube."""
    return cube.to_level_dataframe()
