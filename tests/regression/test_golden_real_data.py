"""Golden-value regression tests pinned from the current implementation.

**What these numbers are.**  Every constant below was computed *once* by the
current AcousticBench implementation from the published ``Data.mat``
(Zenodo DOI 10.5281/zenodo.20023285) and is pinned here with a small tolerance.
They guard against accidental numerical/behavioural drift in the measurement,
aggregation and statistics layers on **this specific dataset**.

**What these numbers are NOT.**  They are *not* physical truth or a
calibration reference.  Some quantities (e.g. REOIG) rely on documented
interpretation choices (in-situ free-field reference, reference-probe
placement bias); changing those documented choices would legitimately change
the golden values.  Any deliberate algorithm change must re-derive them in the
same commit and explain why in the changelog/NEWS.

The SHA-256 of the dataset is pinned as published (see ``DATA_LICENSE.md``).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from acousticbench.measurements.ptpe import (
    ptpe_hha_band_levels,
    ptpe_reoig_band_levels,
    ptpe_summary,
    ptpe_threshold_db,
    probe_bias_db,
)
from acousticbench.measurements.transfer import (
    feedback_path_db_spl,
    hha_db_spl,
    reoig_db,
    reug_db,
)
from acousticbench.stats.bands import octave_bands
from acousticbench.types import Condition, Probe

pytestmark = pytest.mark.regression

# ---------------------------------------------------------------------------
# pinned constants (computed from the implementation on the published dataset)
# ---------------------------------------------------------------------------
KNOWN_DATA_SHA256 = "45cf5eeb83c659489a6dc981a59ae4fe045f2df2bbe6ebb084139dc3d5333e48"

#: Median Hha of the closed earmold (measurement probe, measurement condition)
#: at the DFT bin closest to 1 kHz (1001.29 Hz), in dB SPL at 11.2 mV drive.
HHA_CLOSED_1KHZ_DB_SPL = 76.13934448012914
#: Same curve at the bin closest to 4 kHz.
HHA_CLOSED_4KHZ_DB_SPL = 79.18649629349076
#: Median REOIG of the closed earmold at the bin closest to 1 kHz.
REOIG_CLOSED_1KHZ_DB = -10.915445930981383
#: PTPE on Hha for the nugget earmold in the 63 Hz octave band, from
#: ``ptpe_summary`` (median across subjects of subject-level reinsertion means).
PTPE_HHA_NUGGET_63HZ_DB = -11.5596044402881
#: PTPE on REOIG for the closed earmold in the 1 kHz octave band, from
#: ``ptpe_summary``.
PTPE_REOIG_CLOSED_1KHZ_DB = 3.3244639551684316
#: PTPE on thresholds for the closed earmold at 125 Hz, computed as the mean
#: across subjects of the subject-level reinsertion mean of ``T_ref - T_meas``.
PTPE_THRESHOLD_CLOSED_125HZ_DB = -3.892857142857143
#: Median feedback-path level (M_ha2haf, dB SPL at 11.2 mV).
FEEDBACK_MEDIAN_DB_SPL = 22.90259599415027
#: Median REUG between 2 and 4 kHz (dB re the in-situ free field).
REUG_MEDIAN_2_4KHZ_DB = 16.531181257640977
#: Median absolute MPT-RPT probe bias between 0.5 and 4 kHz (dB).
PROBE_BIAS_ABS_MEDIAN_500_4000HZ_DB = 1.7677663421199838

#: Tolerance of the aggregate golden values (dB).  Machine/platform variation
#: of the underlying NumPy/SciPy linear algebra is far below this.
_TOL_DB = 0.02
_TOL_AGGREGATE_DB = 0.05


def _nearest(curve, frequency_hz: float):
    return curve.loc[np.argmin(np.abs(curve["frequency_hz"] - frequency_hz))]


# ---------------------------------------------------------------------------
# dataset provenance
# ---------------------------------------------------------------------------
@pytest.mark.requires_data
def test_dataset_sha256_matches_published_value(dataset_hashed):
    assert dataset_hashed.info.sha256 == KNOWN_DATA_SHA256
    assert dataset_hashed.info.mat_format == "v5"
    assert dataset_hashed.info.size_bytes > 80 * 1024**2


# ---------------------------------------------------------------------------
# level curves
# ---------------------------------------------------------------------------
@pytest.mark.requires_data
def test_hha_closed_earmold_1khz_golden(dataset):
    curve = hha_db_spl(
        dataset,
        probe=Probe.MEASUREMENT,
        condition=Condition.MEASUREMENT,
        families=["closed_earmold"],
    ).median_level_curve()
    row = _nearest(curve, 1000.0)
    assert row["frequency_hz"] == pytest.approx(1001.2939453125)
    assert float(row["median_db"]) == pytest.approx(HHA_CLOSED_1KHZ_DB_SPL, abs=_TOL_DB)


@pytest.mark.requires_data
def test_hha_closed_earmold_4khz_golden(dataset):
    curve = hha_db_spl(
        dataset,
        probe=Probe.MEASUREMENT,
        condition=Condition.MEASUREMENT,
        families=["closed_earmold"],
    ).median_level_curve()
    row = _nearest(curve, 4000.0)
    assert float(row["median_db"]) == pytest.approx(HHA_CLOSED_4KHZ_DB_SPL, abs=_TOL_DB)


@pytest.mark.requires_data
def test_reoig_closed_earmold_1khz_golden(dataset):
    curve = reoig_db(
        dataset,
        condition=Condition.MEASUREMENT,
        probe=Probe.MEASUREMENT,
        families=["closed_earmold"],
    ).median_level_curve()
    row = _nearest(curve, 1000.0)
    assert float(row["median_db"]) == pytest.approx(REOIG_CLOSED_1KHZ_DB, abs=_TOL_DB)


@pytest.mark.requires_data
def test_feedback_path_median_golden(dataset):
    cube = feedback_path_db_spl(dataset, condition=Condition.MEASUREMENT)
    assert float(np.nanmedian(cube.values)) == pytest.approx(
        FEEDBACK_MEDIAN_DB_SPL, abs=_TOL_AGGREGATE_DB
    )


@pytest.mark.requires_data
def test_reug_2_4khz_golden(dataset):
    frame = reug_db(dataset).to_dataframe(valid_only=True)
    band = frame.loc[(frame["frequency_hz"] >= 2000.0) & (frame["frequency_hz"] <= 4000.0)]
    assert float(np.nanmedian(band["value"])) == pytest.approx(
        REUG_MEDIAN_2_4KHZ_DB, abs=0.1
    )


# ---------------------------------------------------------------------------
# probe-tube presence effect (PTPE)
# ---------------------------------------------------------------------------
@pytest.mark.requires_data
def test_ptpe_hha_nugget_63hz_golden(dataset):
    summary = ptpe_summary(dataset, octave_bands())
    row = summary.loc[
        (summary["metric"] == "delta_hha")
        & (summary["family"] == "nugget_earmold")
        & (summary["band_center_hz"] == 63.0)
    ]
    assert len(row) == 1
    assert float(row["value_db"].iloc[0]) == pytest.approx(
        PTPE_HHA_NUGGET_63HZ_DB, abs=0.1
    )
    assert int(row["n_subjects"].iloc[0]) == 14


@pytest.mark.requires_data
def test_ptpe_reoig_closed_1khz_golden(dataset):
    summary = ptpe_summary(dataset, octave_bands())
    row = summary.loc[
        (summary["metric"] == "delta_reoig")
        & (summary["family"] == "closed_earmold")
        & (summary["band_center_hz"] == 1000.0)
    ]
    assert len(row) == 1
    assert float(row["value_db"].iloc[0]) == pytest.approx(
        PTPE_REOIG_CLOSED_1KHZ_DB, abs=0.1
    )


@pytest.mark.requires_data
def test_ptpe_threshold_closed_125hz_golden(dataset):
    cube = ptpe_threshold_db(dataset)
    index = int(np.argmin(np.abs(cube.freq_hz - 125.0)))
    families = np.array([device.family for device in cube.devices])
    values = cube.masked[index][families == "closed_earmold"][0]  # (subjects, reinsertions)
    subject_means = np.nanmean(values, axis=1)
    assert int(np.isfinite(subject_means).sum()) == 14
    assert float(np.nanmean(subject_means)) == pytest.approx(
        PTPE_THRESHOLD_CLOSED_125HZ_DB, abs=_TOL_AGGREGATE_DB
    )
    # The independent band-level aggregation must tell the same story.
    band_frame = ptpe_hha_band_levels(dataset, octave_bands())
    band_row = band_frame.loc[
        (band_frame["family"] == "closed_earmold")
        & (band_frame["band_center_hz"] == 125.0)
        & band_frame["valid"]
    ]
    assert float(np.nanmedian(band_row["ptpe_db"])) < 0.0


@pytest.mark.requires_data
def test_probe_bias_golden(dataset):
    cube = probe_bias_db(dataset, condition=Condition.MEASUREMENT)
    band = cube.select(freq_range=(500.0, 4000.0))
    assert float(np.nanmedian(np.abs(band.values))) == pytest.approx(
        PROBE_BIAS_ABS_MEDIAN_500_4000HZ_DB, abs=0.2
    )
    reoig_band = ptpe_reoig_band_levels(dataset, octave_bands())
    reoig_band = reoig_band.loc[reoig_band["valid"]]
    mid = reoig_band.loc[
        (reoig_band["family"] == "closed_earmold") & (reoig_band["band_center_hz"] == 1000.0)
    ]
    assert float(np.nanmedian(mid["ptpe_db"])) == pytest.approx(
        PTPE_REOIG_CLOSED_1KHZ_DB, abs=0.1
    )


# ---------------------------------------------------------------------------
# audit summary + committed experiment artefacts
# ---------------------------------------------------------------------------
@pytest.mark.requires_data
def test_audit_summary_golden(dataset):
    audit = dataset.audit()
    assert audit.n_errors == 0
    assert audit.n_warnings == 0
    assert len(audit.findings) == 17
    assert audit.passed is True


def test_experiment_index_has_sixteen_completed_rows(repo_root):
    index_csv = repo_root / "results" / "experiments" / "experiment_index.csv"
    if not index_csv.is_file():
        pytest.skip(f"No committed experiment index at {index_csv}")
    import pandas as pd

    index = pd.read_csv(index_csv)
    assert len(index) == 16
    assert list(index["code"]) == [f"E{i:02d}" for i in range(1, 17)]
    assert (index["status"] == "completed").all(), index.loc[
        index["status"] != "completed", ["code", "status", "error"]
    ].to_dict(orient="records")
    assert (index["error"].fillna("") == "").all()
    for directory in index["directory"]:
        experiment_dir = repo_root / "results" / "experiments" / str(directory)
        assert experiment_dir.is_dir(), experiment_dir
        assert (experiment_dir / "result.json").is_file()
        payload = json.loads((experiment_dir / "result.json").read_text(encoding="utf-8"))
        assert payload["status"] == "completed"

    index_json = repo_root / "results" / "experiments" / "experiment_index.json"
    assert index_json.is_file()
    payload = json.loads(index_json.read_text(encoding="utf-8"))
    assert len(payload["experiments"]) == 16
    assert all(entry["status"] == "completed" for entry in payload["experiments"])
