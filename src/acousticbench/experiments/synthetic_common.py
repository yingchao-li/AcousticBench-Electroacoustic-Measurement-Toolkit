"""Helpers for the synthetic-signal validation experiments E09–E12.

The 1000-case suite is a deterministic 4 × 250 factorial: 250 cases for each of
gain, SNR, THD and frequency-response estimation.  Forty percent of each
category is generated inside the documented *reference condition* for its
metric; the remaining cases probe a wider parameter range and are reported
separately, never merged into the headline target.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from acousticbench.config import Config
from acousticbench.synthetic import SyntheticCase, build_cases, save_manifest

__all__ = [
    "build_suite",
    "category_cases",
    "error_summary",
    "reference_cases",
]


def build_suite(config: Config, *, persist_manifest: bool = True) -> tuple[SyntheticCase, ...]:
    """Build the deterministic synthetic suite described by the configuration."""
    synthetic = config.synthetic
    cases = build_cases(
        n_cases=int(synthetic.n_cases),
        seed=int(synthetic.seed),
        fs_hz=int(synthetic.fs_hz),
    )
    if persist_manifest:
        manifest_dir = config.results_dir / "synthetic"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        save_manifest(cases, manifest_dir)
    return cases


def category_cases(cases: Sequence[SyntheticCase], category: str) -> tuple[SyntheticCase, ...]:
    selected = tuple(case for case in cases if case.category == category)
    if not selected:
        raise ValueError(f"No synthetic cases for category {category!r}")
    return selected


def reference_cases(cases: Iterable[SyntheticCase]) -> tuple[SyntheticCase, ...]:
    return tuple(case for case in cases if case.is_reference_condition)


def error_summary(
    errors: np.ndarray | Sequence[float],
    target: float,
    *,
    unit: str,
) -> dict[str, object]:
    """Summarise absolute errors against a preset target.

    Only finite errors are summarised; the number of evaluated cases is
    reported so that a partially failed evaluation cannot be mistaken for a
    complete one.
    """
    values = np.abs(np.asarray(list(errors), dtype=float))
    values = values[np.isfinite(values)]
    target_value = float(target)
    if values.size == 0:
        return {
            "n": 0,
            "median_abs_error": None,
            "mean_abs_error": None,
            "p95_abs_error": None,
            "max_abs_error": None,
            "fraction_within_target": None,
            "target": target_value,
            "unit": unit,
            "target_met": False,
        }
    fraction = float(np.mean(values <= target_value))
    return {
        "n": int(values.size),
        "median_abs_error": float(np.median(values)),
        "mean_abs_error": float(np.mean(values)),
        "p95_abs_error": float(np.percentile(values, 95)),
        "max_abs_error": float(np.max(values)),
        "fraction_within_target": fraction,
        "target": target_value,
        "unit": unit,
        "target_met": bool(fraction == 1.0),
    }


def error_dataframe(rows: Sequence[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values("case_id").reset_index(drop=True)
    return frame
