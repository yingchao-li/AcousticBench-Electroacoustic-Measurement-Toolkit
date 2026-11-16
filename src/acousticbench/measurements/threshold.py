"""Hearing-threshold analysis.

Thresholds are stored as the receiver voltage at threshold in dBV at 125, 250,
500, 750, 1000 and 2000 Hz.  Lower dBV means a more sensitive coupling (less
voltage needed).  Thresholds are quantised to 1 dB by the measurement
procedure, which limits the resolution of threshold-based effect estimates
(see docs/data.md).
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from acousticbench.data.dataset import AcousticDataset, TransferCube
from acousticbench.types import Condition, DEVICES

__all__ = [
    "audiogram_summary",
    "threshold_curve",
    "threshold_difference_table",
    "threshold_table",
]


def threshold_table(
    dataset: AcousticDataset,
    *,
    conditions: Iterable[Condition | str] | None = None,
    families: Iterable[str] | None = None,
    subjects: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Tidy table of valid thresholds (dBV)."""
    cube = dataset.threshold(
        conditions=conditions,
        families=families,
        subjects=subjects,
    )
    frame = cube.to_dataframe(valid_only=True)
    frame["threshold_dbv"] = frame["value"].astype(float)
    return frame.drop(columns=["value"])


def threshold_curve(
    dataset: AcousticDataset,
    *,
    conditions: Iterable[Condition | str] | None = None,
    families: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Median threshold curve per family/condition across subjects/reinsertions.

    Columns: ``family, family_label, condition, frequency_hz, median_dbv,
    mean_dbv, sd_dbv, n_subjects``.
    """
    frame = threshold_table(dataset, conditions=conditions, families=families)
    grouped = (
        frame.groupby(
            ["family", "family_label", "condition", "threshold_frequency_hz"],
            as_index=False,
        )
        .agg(
            median_dbv=("threshold_dbv", "median"),
            mean_dbv=("threshold_dbv", "mean"),
            sd_dbv=("threshold_dbv", "std"),
            n_subjects=("subject", "nunique"),
        )
        .rename(columns={"threshold_frequency_hz": "frequency_hz"})
    )
    return grouped


def audiogram_summary(dataset: AcousticDataset) -> pd.DataFrame:
    """Threshold per family/condition/frequency averaged over subjects and reinsertions."""
    frame = threshold_table(dataset)
    summary = (
        frame.groupby(
            ["family", "family_label", "condition", "threshold_frequency_hz"],
            as_index=False,
        )
        .agg(
            mean_dbv=("threshold_dbv", "mean"),
            median_dbv=("threshold_dbv", "median"),
            sd_dbv=("threshold_dbv", "std"),
            n=("threshold_dbv", "size"),
        )
        .rename(columns={"threshold_frequency_hz": "frequency_hz"})
    )
    return summary


def threshold_difference_table(dataset: AcousticDataset) -> pd.DataFrame:
    """ΔT = T(reference) − T(measurement) per family/subject/reinsertion/frequency.

    Positive values indicate a *lower* threshold voltage in the measurement
    condition.  Note that the physically meaningful "probe insertion reduces
    the driver output" effect corresponds to **negative** ΔT (as defined in
    the source publication).
    """
    reference_codes = [d.code for d in DEVICES if d.condition is Condition.REFERENCE]
    measurement_codes = [d.code for d in DEVICES if d.condition is Condition.MEASUREMENT]
    reference = dataset.threshold(device_codes=reference_codes).values
    measurement = dataset.threshold(device_codes=measurement_codes).values
    valid = np.isfinite(reference) & np.isfinite(measurement)
    values = reference - measurement
    family_rows: list[pd.DataFrame] = []
    for index, device in enumerate(
        [d for d in DEVICES if d.condition is Condition.REFERENCE]
    ):
        measurement_device = DEVICES[2 * index + 1]
        data = values[:, index, :, :]
        valid_data = valid[:, index, :, :]
        n_freq, n_subject, n_reinsertion = data.shape
        family_rows.append(
            pd.DataFrame(
                {
                    "family": device.family,
                    "family_label": device.family_label,
                    "subject": np.tile(np.repeat(np.arange(1, n_subject + 1), n_reinsertion), n_freq),
                    "reinsertion": np.tile(
                        np.arange(1, n_reinsertion + 1), n_freq * n_subject
                    ),
                    "threshold_frequency_hz": np.repeat(
                        dataset.threshold_frequency_hz, n_subject * n_reinsertion
                    ),
                    "t_reference_dbv": reference[:, index, :, :].reshape(-1),
                    "t_measurement_dbv": measurement[:, index, :, :].reshape(-1),
                    "delta_t_db": data.reshape(-1),
                    "valid": valid_data.reshape(-1),
                    "measurement_device_code": measurement_device.code,
                }
            )
        )
    result = pd.concat(family_rows, ignore_index=True)
    return result.loc[result["valid"]].drop(columns=["valid"]).reset_index(drop=True)
