"""Unit tests for :mod:`acousticbench.config`.

Covers the default configuration, dotted-key access, recursive merging,
validation of invalid settings, experiment parameters, repository-root and
path resolution.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from acousticbench.config import (
    AnalysisConfig,
    Config,
    config_from_mapping,
    deep_merge,
    load_config,
    repo_root,
)
from acousticbench.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------
def test_project_defaults(config):
    assert isinstance(config, Config)
    assert config.project.name == "AcousticBench"
    assert config.project.version == "0.1.0"
    assert config.project.seed == 20260422
    assert config.project.description


def test_data_defaults(config):
    data = config.data
    assert data.n_subjects == 14
    assert data.n_reinsertions == 3
    assert data.n_devices == 14
    assert data.n_frequencies == 2049
    assert data.n_threshold_frequencies == 6
    assert data.invalid_policy == "exclude"
    assert data.min_analysis_frequency_hz == pytest.approx(50.0)
    assert data.fft_bin_count == 4096
    assert data.free_field_reference.min_devices == 5
    assert data.free_field_reference.method == "reference_condition_measurement_probe_median"
    assert data.threshold_quantisation_db == pytest.approx(1.0)


def test_analysis_defaults(config):
    analysis = config.analysis
    assert analysis.alpha == pytest.approx(0.05)
    assert analysis.correction == "holm"
    assert analysis.unit_of_analysis == "subject"
    assert analysis.bootstrap.n_resamples == 10000
    assert analysis.bootstrap.confidence == pytest.approx(0.95)
    assert analysis.bootstrap.method == "percentile"
    assert analysis.bands.method == "octave"
    assert analysis.bands.custom_edges_hz == (20.0, 100.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0, 22050.0)
    assert analysis.smoothing.method == "none"
    assert analysis.level_floor_db == pytest.approx(-120.0)
    assert analysis.summary_bands_hz == (100, 250, 500, 1000, 2000, 4000, 8000)
    assert analysis.primary_band_hz == (500.0, 4000.0)
    assert analysis.minimum_subjects == 3


def test_synthetic_and_experiment_defaults(config):
    assert config.synthetic.n_cases == 1000
    assert config.synthetic.fs_hz == 48000
    assert config.synthetic.snr_db_range == (0.0, 40.0)
    assert config.synthetic.filter_types == ("lowpass", "highpass", "bandpass", "peaking")
    assert config.synthetic.targets["gain_error_db"] == pytest.approx(0.1)
    expected_codes = tuple(f"E{i:02d}" for i in range(1, 17))
    assert config.experiments.enabled == expected_codes
    assert config.experiments.figure_format == "png"
    assert config.experiments.figure_dpi == 150
    assert config.dashboard.cache_ttl_s == 3600
    assert config.report.page_size == "A4"


def test_logging_defaults(config):
    assert config.logging.level == "INFO"
    assert config.logging.file == "results/logs/acousticbench.log"


# ---------------------------------------------------------------------------
# dotted access / merging
# ---------------------------------------------------------------------------
def test_dotted_get(config):
    assert config.get("analysis.bootstrap.n_resamples") == 10000
    assert config.get("analysis.bootstrap") is config.raw["analysis"]["bootstrap"]
    assert config.get("data.free_field_reference.method") == (
        "reference_condition_measurement_probe_median"
    )
    assert config.get("analysis.alpha") == pytest.approx(0.05)


def test_dotted_get_missing_returns_default(config):
    assert config.get("does.not.exist") is None
    assert config.get("does.not.exist", 42) == 42
    # A scalar node cannot be traversed further.
    assert config.get("analysis.alpha.nested", "fallback") == "fallback"
    assert config.get("", "empty") == "empty"


def test_deep_merge_recursive():
    base = {"a": 1, "nested": {"x": 1, "y": 2, "deep": {"k": "v"}}, "items": [1, 2]}
    override = {"nested": {"y": 20, "deep": {"k": "w", "extra": True}}, "items": [9]}
    merged = deep_merge(base, override)
    assert merged == {
        "a": 1,
        "nested": {"x": 1, "y": 20, "deep": {"k": "w", "extra": True}},
        "items": [9],
    }
    # Inputs are not mutated and the result is a deep copy.
    assert base["nested"]["y"] == 2
    assert base["items"] == [1, 2]
    merged["nested"]["deep"]["k"] = "mutated"
    assert base["nested"]["deep"]["k"] == "v"


def test_load_config_overrides_are_merged():
    cfg = load_config(overrides={"analysis": {"alpha": 0.01}, "project": {"seed": 7}})
    assert cfg.analysis.alpha == pytest.approx(0.01)
    assert cfg.project.seed == 7
    # Unrelated keys are preserved.
    assert cfg.analysis.correction == "holm"
    assert cfg.analysis.bootstrap.n_resamples == 10000
    assert cfg.get("analysis.alpha") == pytest.approx(0.01)


def test_load_config_user_yaml_file(tmp_path):
    user = tmp_path / "user.yaml"
    user.write_text(
        yaml.safe_dump({"paths": {"results_dir": "custom_results"}, "analysis": {"alpha": 0.2}}),
        encoding="utf-8",
    )
    cfg = load_config(user)
    assert cfg.analysis.alpha == pytest.approx(0.2)
    assert cfg.paths.results_dir == "custom_results"
    assert cfg.results_dir == cfg.root / "custom_results"
    assert cfg.source_files[0].name == "default.yaml"
    assert cfg.source_files[-1] == user.resolve()


def test_load_config_empty_user_yaml_is_allowed(tmp_path):
    user = tmp_path / "empty.yaml"
    user.write_text("", encoding="utf-8")
    cfg = load_config(user)
    assert cfg.project.name == "AcousticBench"


def test_load_config_uses_env_config(monkeypatch, tmp_path):
    user = tmp_path / "env.yaml"
    user.write_text(yaml.safe_dump({"analysis": {"alpha": 0.123}}), encoding="utf-8")
    monkeypatch.setenv("ACOUSTICBENCH_CONFIG", str(user))
    cfg = load_config()
    assert cfg.analysis.alpha == pytest.approx(0.123)


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(ConfigurationError, match="not found"):
        load_config(tmp_path / "missing.yaml")


def test_invalid_yaml_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("analysis: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Invalid YAML"):
        load_config(bad)


def test_non_mapping_root_raises(tmp_path):
    bad = tmp_path / "list.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="mapping"):
        load_config(bad)


# ---------------------------------------------------------------------------
# validation of invalid values
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.5, 2.0])
def test_invalid_alpha_raises(alpha):
    with pytest.raises(ConfigurationError, match="alpha"):
        load_config(overrides={"analysis": {"alpha": alpha}})


@pytest.mark.parametrize("confidence", [0.0, 0.49, 1.0, 1.5])
def test_invalid_bootstrap_confidence_raises(confidence):
    with pytest.raises(ConfigurationError, match="confidence"):
        load_config(overrides={"analysis": {"bootstrap": {"confidence": confidence}}})


@pytest.mark.parametrize("n_resamples", [1, 10, 99, 0, -5])
def test_invalid_bootstrap_resamples_raises(n_resamples):
    with pytest.raises(ConfigurationError, match="n_resamples"):
        load_config(overrides={"analysis": {"bootstrap": {"n_resamples": n_resamples}}})


def test_invalid_primary_band_raises():
    with pytest.raises(ConfigurationError, match="primary_band_hz"):
        load_config(overrides={"analysis": {"primary_band_hz": [500, 1000, 4000]}})


def test_invalid_band_edges_raise():
    with pytest.raises(ConfigurationError, match="custom_edges_hz"):
        load_config(
            overrides={
                "analysis": {
                    "bands": {"method": "custom", "custom_edges_hz": [1000, "not-a-number"]}
                }
            }
        )


def test_unknown_band_method_raises():
    from acousticbench.stats.bands import bands_from_config

    cfg = load_config(overrides={"analysis": {"bands": {"method": "banana"}}})
    with pytest.raises(ConfigurationError, match="band method"):
        bands_from_config(cfg)


def test_custom_bands_are_parsed():
    from acousticbench.stats.bands import bands_from_config

    cfg = load_config(
        overrides={
            "analysis": {"bands": {"method": "custom", "custom_edges_hz": [100, 1000, 4000]}}
        }
    )
    bands = bands_from_config(cfg)
    assert [band.label for band in bands] == ["100–1000 Hz", "1000–4000 Hz"]
    assert cfg.analysis.bands.custom_edges_hz == (100.0, 1000.0, 4000.0)


def test_invalid_synthetic_n_cases_raises():
    with pytest.raises(ConfigurationError, match="n_cases"):
        load_config(overrides={"synthetic": {"n_cases": 0}})


@pytest.mark.parametrize(
    "overrides",
    [
        {"project": {"seed": "not-an-int"}},
        {"analysis": {"alpha": "not-a-float"}},
        {"analysis": {"bootstrap": {"confidence": "bad"}}},
        {"data": {"n_subjects": "many"}},
        {"experiments": {"figure_dpi": "high"}},
        {"dashboard": {"default_band_hz": ["a", "b"]}},
    ],
)
def test_invalid_value_types_raise(overrides):
    with pytest.raises(ConfigurationError):
        load_config(overrides=overrides)


def test_config_from_mapping_defaults():
    cfg = config_from_mapping({}, root=Path("/tmp/root"))
    assert cfg.root == Path("/tmp/root")
    assert cfg.project.name == "AcousticBench"
    assert cfg.data.min_analysis_frequency_hz == pytest.approx(20.0)
    assert cfg.analysis.alpha == pytest.approx(0.05)
    assert cfg.experiments.enabled == ()
    assert cfg.source_files == ()


def test_config_is_immutable(config):
    with pytest.raises(Exception):
        config.analysis = AnalysisConfig()  # type: ignore[misc]
    with pytest.raises(Exception):
        config.project.name = "Other"  # type: ignore[misc]


def test_experiment_params(config):
    params = config.experiment_params("E02")
    assert params["report_frequencies_hz"] == [100, 250, 500, 1000, 2000, 4000, 8000]
    assert params["ptpe_frequencies_hz"] == [100, 250, 500, 1000]
    assert config.experiment_params("E07")["frequencies_hz"] == [125, 250, 500, 750, 1000, 2000]
    assert config.experiment_params("E99") == {}


def test_experiment_params_returns_copy(config):
    params = config.experiment_params("E09")
    params["n_cases"] = 1
    assert config.experiment_params("E09")["n_cases"] == 250


def test_with_overrides_returns_new_config(config):
    new = config.with_overrides({"analysis": {"alpha": 0.01}})
    assert new is not config
    assert new.analysis.alpha == pytest.approx(0.01)
    assert config.analysis.alpha == pytest.approx(0.05)
    assert new.root == config.root
    assert new.project.name == config.project.name


# ---------------------------------------------------------------------------
# repository root and path resolution
# ---------------------------------------------------------------------------
def test_repo_root_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ACOUSTICBENCH_ROOT", str(tmp_path))
    assert repo_root() == tmp_path.resolve()


def test_repo_root_detects_checkout(monkeypatch):
    monkeypatch.delenv("ACOUSTICBENCH_ROOT", raising=False)
    root = repo_root()
    assert (root / "config" / "default.yaml").is_file()
    assert (root / "src" / "acousticbench").is_dir()


def test_path_resolution(config):
    root = config.root
    assert config.data_path == root / "Data.mat"
    assert config.documentation_path == root / "Documentation.pdf"
    assert config.results_dir == root / "results"
    assert config.reports_dir == root / "reports"
    assert config.cache_dir == root / ".cache"
    assert config.log_file == root / "results" / "logs" / "acousticbench.log"


def test_path_resolution_absolute(tmp_path):
    absolute = tmp_path / "absolute_data.mat"
    cfg = load_config(overrides={"paths": {"data_mat": str(absolute)}})
    assert cfg.data_path == absolute
    assert cfg.data_path.is_absolute()


def test_log_file_override(tmp_path):
    log_file = tmp_path / "logs" / "custom.log"
    cfg = load_config(overrides={"logging": {"file": str(log_file)}})
    assert cfg.log_file == log_file


def test_config_fixture_uses_repo_root(config, repo_root):
    assert config.root == repo_root
    assert config.root.is_dir()


# ---------------------------------------------------------------------------
# frequency-band definitions driven by the configuration
# ---------------------------------------------------------------------------
def test_band_factories():
    from acousticbench.stats.bands import (
        OCTAVE_CENTERS,
        band_mask,
        custom_bands,
        octave_bands,
        third_octave_bands,
    )

    octaves = octave_bands()
    assert octaves[0].label == "63 Hz"  # 31.5 Hz band is below the 50 Hz sweep start
    assert octaves[-1].center_hz == 16000.0
    assert all(band.low_hz < band.center_hz < band.high_hz for band in octaves)
    assert len(octaves) < len(OCTAVE_CENTERS)

    thirds = third_octave_bands()
    assert len(thirds) > len(octaves)
    assert thirds[0].label == "50 Hz"
    assert thirds[0].center_hz == pytest.approx(50.0)

    limited = octave_bands(f_min=100.0, f_max=8000.0, centers=(500.0, 1000.0, 2000.0))
    assert [band.label for band in limited] == ["500 Hz", "1000 Hz", "2000 Hz"]

    custom = custom_bands([20.0, 100.0, 1000.0])
    assert [band.label for band in custom] == ["20–100 Hz", "100–1000 Hz"]
    assert custom[0].center_hz == pytest.approx(np.sqrt(20.0 * 100.0))
    assert custom[1].center_hz == pytest.approx(np.sqrt(100.0 * 1000.0))
    # The DC edge falls back to the geometric half-power centre.
    assert custom_bands([0.0, 100.0])[0].center_hz == pytest.approx(100.0 / np.sqrt(2.0))

    frequencies = np.array([10.0, 100.0, 500.0, 999.0, 1000.0])
    np.testing.assert_array_equal(
        band_mask(frequencies, custom[1]), custom[1].contains(frequencies)
    )
    assert band_mask(frequencies, custom[0]).tolist() == [False, False, False, False, False]
    assert band_mask(frequencies, custom[1]).tolist() == [False, True, True, True, False]

    with pytest.raises(ConfigurationError, match="1-D sequence"):
        custom_bands([100.0])
    with pytest.raises(ConfigurationError, match="strictly increasing"):
        custom_bands([1000.0, 100.0, 2000.0])


def test_bands_from_config_third_octave_and_custom():
    from acousticbench.stats.bands import bands_from_config, third_octave_bands

    third = load_config(overrides={"analysis": {"bands": {"method": "third_octave"}}})
    assert bands_from_config(third) == third_octave_bands()
    custom = load_config(
        overrides={
            "analysis": {"bands": {"method": "custom", "custom_edges_hz": [100, 2000]}}
        }
    )
    assert [band.label for band in bands_from_config(custom)] == ["100–2000 Hz"]
    empty_custom = load_config(
        overrides={"analysis": {"bands": {"method": "custom", "custom_edges_hz": []}}}
    )
    with pytest.raises(ConfigurationError, match="custom_edges_hz"):
        bands_from_config(empty_custom)
