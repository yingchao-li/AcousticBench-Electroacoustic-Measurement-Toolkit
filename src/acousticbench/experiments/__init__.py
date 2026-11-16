"""The sixteen reproducible experiments E01–E16.

Typical use::

    from acousticbench.config import load_config
    from acousticbench.experiments import ExperimentRunner
    runner = ExperimentRunner(load_config())
    results = runner.run_all(["E01", "E02"])
    print(results[0].metrics)

Artifacts are written under ``results/experiments/<code>_<slug>/``.
"""

from acousticbench.experiments.base import (
    Experiment,
    ExperimentContext,
    ExperimentResult,
    ExperimentRunner,
    ExperimentSpec,
)
from acousticbench.experiments.registry import EXPERIMENTS

__all__ = [
    "EXPERIMENTS",
    "Experiment",
    "ExperimentContext",
    "ExperimentResult",
    "ExperimentRunner",
    "ExperimentSpec",
]
