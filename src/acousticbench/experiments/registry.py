"""Experiment registry.

Importing this module registers all implemented experiments.  The runner uses
the registry to resolve codes such as ``"E01"``.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from acousticbench.experiments.base import ExperimentSpec

_MODULES: tuple[str, ...] = (
    "acousticbench.experiments.e01_frequency_response",
    "acousticbench.experiments.e02_probe_tube_bias",
    "acousticbench.experiments.e03_repeatability",
    "acousticbench.experiments.e04_inter_subject_variability",
    "acousticbench.experiments.e05_acoustic_feedback",
    "acousticbench.experiments.e06_real_ear_response",
    "acousticbench.experiments.e07_hearing_threshold",
    "acousticbench.experiments.e08_statistical_comparison",
    "acousticbench.experiments.e09_gain_estimation",
    "acousticbench.experiments.e10_thd_estimation",
    "acousticbench.experiments.e11_snr_estimation",
    "acousticbench.experiments.e12_filter_response_estimation",
    "acousticbench.experiments.e13_dynamic_compression",
    "acousticbench.experiments.e14_fault_injection",
    "acousticbench.experiments.e15_matlab_python_agreement",
    "acousticbench.experiments.e16_runtime_benchmark",
)


def _load(module_name: str) -> ModuleType:
    return importlib.import_module(module_name)


def _build_registry() -> dict[str, ExperimentSpec]:
    registry: dict[str, ExperimentSpec] = {}
    for module_name in _MODULES:
        module = _load(module_name)
        code = getattr(module, "CODE", None)
        title = getattr(module, "TITLE", None)
        runner = getattr(module, "run", None)
        if not (code and title and callable(runner)):
            raise RuntimeError(
                f"Experiment module {module_name!r} must define CODE, TITLE and run(context)"
            )
        if code in registry:
            raise RuntimeError(f"Duplicate experiment code {code!r}")
        registry[code] = ExperimentSpec(
            code=code,
            title=title,
            description=getattr(module, "DESCRIPTION", ""),
            runner=runner,
            module=module_name,
        )
    return registry


#: Registry of all experiments, populated at import time.
EXPERIMENTS: dict[str, ExperimentSpec] = _build_registry()

#: Registry keyed by import path (for plugin-style discovery).
MODULES = _MODULES
