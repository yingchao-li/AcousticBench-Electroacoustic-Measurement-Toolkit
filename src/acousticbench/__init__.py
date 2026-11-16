"""AcousticBench — Electroacoustic Measurement, Validation & Reporting Toolkit.

A modular, open, reproducible toolkit for the analysis of electroacoustic
measurement data (hearing-aid real-ear measurements), for synthetic signal
processing validation, and for automated engineering reports.

The package is organised in layers:

``acousticbench.types``
    Immutable domain metadata (devices, probes, conditions, containers).
``acousticbench.io``
    MAT-file loading and schema validation.
``acousticbench.data``
    Dataset abstraction, unit conversions, validity rules and data auditing.
``acousticbench.measurements``
    Physical measurement quantities (Hha, REOIG, PTPE, feedback, thresholds).
``acousticbench.stats``
    Subject-level paired statistics, effect sizes and bootstrap confidence
    intervals.
``acousticbench.dsp``
    FFT/STFT/PSD, filtering and signal metrics (gain, SNR, THD, THD+N).
``acousticbench.virtual_ha``
    A deterministic virtual hearing aid (multiband compression, noise, faults).
``acousticbench.synthetic``
    Reproducible synthetic test cases with known ground truth.
``acousticbench.experiments``
    The sixteen reproducible experiments E01–E16.
``acousticbench.validation``
    MATLAB/Python cross-language numerical consistency checks.
``acousticbench.report``
    PDF / Excel / HTML report generation.
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "AcousticBench contributors"

from acousticbench.config import Config, load_config
from acousticbench.data.dataset import AcousticDataset, TransferCube, load_dataset

__all__ = [
    "__version__",
    "AcousticDataset",
    "TransferCube",
    "Config",
    "load_config",
    "load_dataset",
]
