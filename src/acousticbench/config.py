"""Typed configuration loading.

The single source of truth is ``config/default.yaml``.  A user can supply an
additional YAML file (``--config`` / ``ACOUSTICBENCH_CONFIG``) which is merged
recursively over the defaults, and programmatic overrides can be passed as a
nested mapping.

Example
-------
>>> cfg = load_config()
>>> cfg.analysis.bootstrap.n_resamples
10000
>>> cfg.experiment_params("E02")["report_frequencies_hz"]
[100, 250, 500, 1000, 2000, 4000, 8000]
>>> cfg.get("data.free_field_reference.method")
'reference_condition_measurement_probe_median'
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from acousticbench.exceptions import ConfigurationError

_ENV_ROOT = "ACOUSTICBENCH_ROOT"
_ENV_CONFIG = "ACOUSTICBENCH_CONFIG"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def repo_root() -> Path:
    """Return the repository root directory.

    Resolution order:

    1. ``$ACOUSTICBENCH_ROOT`` (explicit override),
    2. the directory two levels above the installed ``acousticbench`` package
       (``src/acousticbench`` → repository root) when it contains a ``config``
       directory,
    3. the current working directory.
    """
    env = os.environ.get(_ENV_ROOT)
    if env:
        return Path(env).expanduser().resolve()
    package_root = Path(__file__).resolve().parents[2]
    if (package_root / "config" / "default.yaml").is_file():
        return package_root
    return Path.cwd().resolve()


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigurationError(f"Configuration root must be a mapping: {path}")
    return data


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base``."""
    result: dict[str, Any] = copy.deepcopy(dict(base))
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(value, Mapping)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# typed sections
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProjectConfig:
    name: str = "AcousticBench"
    version: str = "0.1.0"
    description: str = ""
    seed: int = 20260422


@dataclass(frozen=True)
class PathsConfig:
    data_mat: str = "Data.mat"
    documentation_pdf: str = "Documentation.pdf"
    results_dir: str = "results"
    reports_dir: str = "reports"
    cache_dir: str = ".cache"


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    file: str | None = None


@dataclass(frozen=True)
class BootstrapConfig:
    n_resamples: int = 10000
    confidence: float = 0.95
    seed: int = 20260422
    method: str = "percentile"


@dataclass(frozen=True)
class BandsConfig:
    method: str = "octave"
    custom_edges_hz: tuple[float, ...] = ()


@dataclass(frozen=True)
class SmoothingConfig:
    method: str = "none"
    fraction: int = 3


@dataclass(frozen=True)
class AnalysisConfig:
    alpha: float = 0.05
    correction: str = "holm"
    unit_of_analysis: str = "subject"
    bootstrap: BootstrapConfig = field(default_factory=BootstrapConfig)
    bands: BandsConfig = field(default_factory=BandsConfig)
    smoothing: SmoothingConfig = field(default_factory=SmoothingConfig)
    level_floor_db: float = -120.0
    summary_bands_hz: tuple[float, ...] = (100, 250, 500, 1000, 2000, 4000, 8000)
    primary_band_hz: tuple[float, float] = (500.0, 4000.0)
    minimum_subjects: int = 3


@dataclass(frozen=True)
class FreeFieldReferenceConfig:
    method: str = "reference_condition_measurement_probe_median"
    min_devices: int = 5


@dataclass(frozen=True)
class DataConfig:
    n_subjects: int = 14
    n_reinsertions: int = 3
    n_devices: int = 14
    n_frequencies: int = 2049
    n_threshold_frequencies: int = 6
    invalid_policy: str = "exclude"
    min_analysis_frequency_hz: float = 20.0
    fft_bin_count: int = 4096
    free_field_reference: FreeFieldReferenceConfig = field(
        default_factory=FreeFieldReferenceConfig
    )
    threshold_quantisation_db: float = 1.0


@dataclass(frozen=True)
class SyntheticConfig:
    n_cases: int = 1000
    seed: int = 20260422
    fs_hz: int = 48000
    duration_s: float = 4.0
    snr_db_range: tuple[float, float] = (0.0, 40.0)
    thd_percent_range: tuple[float, float] = (0.1, 10.0)
    gain_db_range: tuple[float, float] = (-20.0, 40.0)
    input_level_dbfs: tuple[float, float] = (-30.0, -10.0)
    filter_types: tuple[str, ...] = ("lowpass", "highpass", "bandpass", "peaking")
    noise_colors: tuple[str, ...] = ("white", "pink")
    targets: Mapping[str, float] = field(default_factory=dict)
    reference_conditions: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentsConfig:
    enabled: tuple[str, ...] = tuple(f"E{i:02d}" for i in range(1, 17))
    figure_format: str = "png"
    figure_dpi: int = 150
    save_tables: bool = True
    save_config_snapshot: bool = True
    params: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class DashboardConfig:
    title: str = "AcousticBench"
    subtitle: str = "Electroacoustic Measurement, Validation & Reporting Toolkit"
    default_condition: str = "measurement"
    default_probe: str = "measurement"
    default_devices: tuple[int, ...] = (2, 4, 6, 8, 10, 12, 14)
    default_band_hz: tuple[float, float] = (500.0, 4000.0)
    max_subjects: int = 14
    cache_ttl_s: int = 3600


@dataclass(frozen=True)
class ReportConfig:
    title: str = "AcousticBench Measurement Report"
    organisation: str = "AcousticBench"
    include_figures: bool = True
    include_appendix: bool = True
    page_size: str = "A4"
    excel_sheets: tuple[str, ...] = (
        "Summary",
        "Data Audit",
        "E01-E04",
        "E05-E08",
        "E09-E12",
        "E13-E16",
        "Statistics",
    )


@dataclass(frozen=True)
class Config:
    """Fully parsed, immutable configuration."""

    root: Path
    project: ProjectConfig
    paths: PathsConfig
    logging: LoggingConfig
    data: DataConfig
    analysis: AnalysisConfig
    synthetic: SyntheticConfig
    experiments: ExperimentsConfig
    dashboard: DashboardConfig
    report: ReportConfig
    raw: Mapping[str, Any] = field(default_factory=dict)
    source_files: tuple[Path, ...] = ()

    # -- convenience path resolution ---------------------------------------
    def _resolve(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (self.root / path)

    @property
    def data_path(self) -> Path:
        return self._resolve(self.paths.data_mat)

    @property
    def documentation_path(self) -> Path:
        return self._resolve(self.paths.documentation_pdf)

    @property
    def results_dir(self) -> Path:
        return self._resolve(self.paths.results_dir)

    @property
    def reports_dir(self) -> Path:
        return self._resolve(self.paths.reports_dir)

    @property
    def cache_dir(self) -> Path:
        return self._resolve(self.paths.cache_dir)

    @property
    def log_file(self) -> Path | None:
        return self._resolve(self.paths.results_dir + "/logs/acousticbench.log") \
            if self.logging.file is None else self._resolve(self.logging.file)

    def experiment_params(self, code: str) -> dict[str, Any]:
        """Return the parameter mapping for one experiment (possibly empty)."""
        return dict(self.experiments.params.get(code, {}))

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Read any raw configuration value with a dotted key."""
        node: Any = self.raw
        for part in dotted_key.split("."):
            if not isinstance(node, Mapping) or part not in node:
                return default
            node = node[part]
        return node

    def with_overrides(self, overrides: Mapping[str, Any]) -> "Config":
        """Return a new configuration with recursive overrides applied."""
        merged = deep_merge(self.raw, overrides)
        return config_from_mapping(merged, root=self.root, source_files=self.source_files)


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def _require(mapping: Mapping[str, Any], key: str, default: Any) -> Any:
    value = mapping.get(key, default)
    return default if value is None else value


def _tuple_float(values: Any, key: str) -> tuple[float, ...]:
    try:
        return tuple(float(v) for v in values)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Expected a list of numbers for {key!r}, got {values!r}") from exc


def config_from_mapping(
    mapping: Mapping[str, Any],
    *,
    root: Path,
    source_files: tuple[Path, ...] = (),
) -> Config:
    """Build a :class:`Config` from a validated nested mapping."""
    try:
        project = mapping.get("project", {})
        paths = mapping.get("paths", {})
        logging_cfg = mapping.get("logging", {})
        data = mapping.get("data", {})
        analysis = mapping.get("analysis", {})
        synthetic = mapping.get("synthetic", {})
        experiments = mapping.get("experiments", {})
        dashboard = mapping.get("dashboard", {})
        report = mapping.get("report", {})

        project_cfg = ProjectConfig(
            name=str(_require(project, "name", "AcousticBench")),
            version=str(_require(project, "version", "0.1.0")),
            description=str(_require(project, "description", "")),
            seed=int(_require(project, "seed", 20260422)),
        )
        paths_cfg = PathsConfig(
            data_mat=str(_require(paths, "data_mat", "Data.mat")),
            documentation_pdf=str(_require(paths, "documentation_pdf", "Documentation.pdf")),
            results_dir=str(_require(paths, "results_dir", "results")),
            reports_dir=str(_require(paths, "reports_dir", "reports")),
            cache_dir=str(_require(paths, "cache_dir", ".cache")),
        )
        logging_config = LoggingConfig(
            level=str(_require(logging_cfg, "level", "INFO")).upper(),
            file=logging_cfg.get("file"),
        )

        ff = data.get("free_field_reference", {}) or {}
        data_cfg = DataConfig(
            n_subjects=int(_require(data, "n_subjects", 14)),
            n_reinsertions=int(_require(data, "n_reinsertions", 3)),
            n_devices=int(_require(data, "n_devices", 14)),
            n_frequencies=int(_require(data, "n_frequencies", 2049)),
            n_threshold_frequencies=int(_require(data, "n_threshold_frequencies", 6)),
            invalid_policy=str(_require(data, "invalid_policy", "exclude")),
            min_analysis_frequency_hz=float(
                _require(data, "min_analysis_frequency_hz", 20.0)
            ),
            fft_bin_count=int(_require(data, "fft_bin_count", 4096)),
            free_field_reference=FreeFieldReferenceConfig(
                method=str(
                    _require(ff, "method", "reference_condition_measurement_probe_median")
                ),
                min_devices=int(_require(ff, "min_devices", 5)),
            ),
            threshold_quantisation_db=float(
                _require(data, "threshold_quantisation_db", 1.0)
            ),
        )

        boot = analysis.get("bootstrap", {}) or {}
        bands = analysis.get("bands", {}) or {}
        smoothing = analysis.get("smoothing", {}) or {}
        analysis_cfg = AnalysisConfig(
            alpha=float(_require(analysis, "alpha", 0.05)),
            correction=str(_require(analysis, "correction", "holm")).lower(),
            unit_of_analysis=str(_require(analysis, "unit_of_analysis", "subject")),
            bootstrap=BootstrapConfig(
                n_resamples=int(_require(boot, "n_resamples", 10000)),
                confidence=float(_require(boot, "confidence", 0.95)),
                seed=int(_require(boot, "seed", project_cfg.seed)),
                method=str(_require(boot, "method", "percentile")),
            ),
            bands=BandsConfig(
                method=str(_require(bands, "method", "octave")),
                custom_edges_hz=_tuple_float(
                    bands.get("custom_edges_hz", []), "analysis.bands.custom_edges_hz"
                ),
            ),
            smoothing=SmoothingConfig(
                method=str(_require(smoothing, "method", "none")),
                fraction=int(_require(smoothing, "fraction", 3)),
            ),
            level_floor_db=float(_require(analysis, "level_floor_db", -120.0)),
            summary_bands_hz=_tuple_float(
                _require(analysis, "summary_bands_hz", [100, 250, 500, 1000, 2000, 4000, 8000]),
                "analysis.summary_bands_hz",
            ),
            primary_band_hz=_tuple_float(
                _require(analysis, "primary_band_hz", [500, 4000]),
                "analysis.primary_band_hz",
            ),
            minimum_subjects=int(_require(analysis, "minimum_subjects", 3)),
        )
        if analysis_cfg.alpha <= 0 or analysis_cfg.alpha >= 1:
            raise ConfigurationError("analysis.alpha must be in (0, 1)")
        if not 0.5 <= analysis_cfg.bootstrap.confidence < 1:
            raise ConfigurationError("analysis.bootstrap.confidence must be in [0.5, 1)")
        if analysis_cfg.bootstrap.n_resamples < 100:
            raise ConfigurationError("analysis.bootstrap.n_resamples must be >= 100")
        if len(analysis_cfg.primary_band_hz) != 2:
            raise ConfigurationError("analysis.primary_band_hz must contain two frequencies")

        synthetic_cfg = SyntheticConfig(
            n_cases=int(_require(synthetic, "n_cases", 1000)),
            seed=int(_require(synthetic, "seed", project_cfg.seed)),
            fs_hz=int(_require(synthetic, "fs_hz", 48000)),
            duration_s=float(_require(synthetic, "duration_s", 4.0)),
            snr_db_range=_tuple_float(
                _require(synthetic, "snr_db_range", [0, 40]), "synthetic.snr_db_range"
            ),
            thd_percent_range=_tuple_float(
                _require(synthetic, "thd_percent_range", [0.1, 10]),
                "synthetic.thd_percent_range",
            ),
            gain_db_range=_tuple_float(
                _require(synthetic, "gain_db_range", [-20, 40]), "synthetic.gain_db_range"
            ),
            input_level_dbfs=_tuple_float(
                _require(synthetic, "input_level_dbfs", [-30, -10]),
                "synthetic.input_level_dbfs",
            ),
            filter_types=tuple(
                str(v) for v in _require(synthetic, "filter_types", ["lowpass"])
            ),
            noise_colors=tuple(str(v) for v in _require(synthetic, "noise_colors", ["white"])),
            targets=dict(synthetic.get("targets", {}) or {}),
            reference_conditions=dict(synthetic.get("reference_conditions", {}) or {}),
        )
        if synthetic_cfg.n_cases < 1:
            raise ConfigurationError("synthetic.n_cases must be >= 1")

        experiments_cfg = ExperimentsConfig(
            enabled=tuple(str(v) for v in _require(experiments, "enabled", [])),
            figure_format=str(_require(experiments, "figure_format", "png")),
            figure_dpi=int(_require(experiments, "figure_dpi", 150)),
            save_tables=bool(_require(experiments, "save_tables", True)),
            save_config_snapshot=bool(_require(experiments, "save_config_snapshot", True)),
            params=dict(experiments.get("params", {}) or {}),
        )

        dashboard_cfg = DashboardConfig(
            title=str(_require(dashboard, "title", "AcousticBench")),
            subtitle=str(_require(dashboard, "subtitle", "")),
            default_condition=str(_require(dashboard, "default_condition", "measurement")),
            default_probe=str(_require(dashboard, "default_probe", "measurement")),
            default_devices=tuple(
                int(v) for v in _require(dashboard, "default_devices", [2, 4, 6, 8])
            ),
            default_band_hz=_tuple_float(
                _require(dashboard, "default_band_hz", [500, 4000]),
                "dashboard.default_band_hz",
            ),
            max_subjects=int(_require(dashboard, "max_subjects", 14)),
            cache_ttl_s=int(_require(dashboard, "cache_ttl_s", 3600)),
        )

        report_cfg = ReportConfig(
            title=str(_require(report, "title", "AcousticBench Measurement Report")),
            organisation=str(_require(report, "organisation", "AcousticBench")),
            include_figures=bool(_require(report, "include_figures", True)),
            include_appendix=bool(_require(report, "include_appendix", True)),
            page_size=str(_require(report, "page_size", "A4")),
            excel_sheets=tuple(
                str(v)
                for v in _require(report, "excel_sheets", ["Summary", "Data Audit"])
            ),
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise ConfigurationError(f"Invalid configuration value: {exc}") from exc

    return Config(
        root=root,
        project=project_cfg,
        paths=paths_cfg,
        logging=logging_config,
        data=data_cfg,
        analysis=analysis_cfg,
        synthetic=synthetic_cfg,
        experiments=experiments_cfg,
        dashboard=dashboard_cfg,
        report=report_cfg,
        raw=mapping,
        source_files=source_files,
    )


def load_config(
    path: str | Path | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
    root: Path | None = None,
) -> Config:
    """Load the default configuration, optionally merged with user overrides.

    Parameters
    ----------
    path:
        Optional user YAML file.  Defaults to ``$ACOUSTICBENCH_CONFIG``.
    overrides:
        Nested mapping merged last (highest priority).
    root:
        Repository root override (defaults to :func:`repo_root`).
    """
    root_dir = (root or repo_root()).resolve()
    default_path = root_dir / "config" / "default.yaml"
    mapping = _read_yaml(default_path)
    sources: list[Path] = [default_path]

    user_path: Path | None = None
    if path is not None:
        user_path = Path(path).expanduser()
    elif os.environ.get(_ENV_CONFIG):
        user_path = Path(os.environ[_ENV_CONFIG]).expanduser()
    if user_path is not None:
        user_mapping = _read_yaml(user_path)
        mapping = deep_merge(mapping, user_mapping)
        sources.append(user_path.resolve())

    if overrides:
        mapping = deep_merge(mapping, overrides)
    return config_from_mapping(mapping, root=root_dir, source_files=tuple(sources))
