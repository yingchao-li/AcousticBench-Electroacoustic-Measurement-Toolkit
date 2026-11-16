"""Shared pytest fixtures for the AcousticBench test-suite.

Design principles
-----------------
* The real 90 MB ``Data.mat`` is **never** required for the bulk of the
  suite.  Fixtures that need it skip with a clear message
  (:func:`pytest.skip`) and every test using them is additionally marked
  ``requires_data`` so that the CI data-free subset
  (``pytest -m "not requires_data"``) also deselects them explicitly.
* A small *synthetic* MAT-file fixture with the documented schema is
  generated with :func:`scipy.io.savemat`.  ``Data.mat`` itself is 90 MB
  because of the 2049 × 14 × 14 × 3 complex containers; the fixture has the
  same (schema-mandated) dimensions but smooth deterministic values, so it
  compresses to ~19 MB and loads in ~0.1 s.
* A second fixture exercises the MATLAB v7.3 (HDF5) loader fallback.
* All matplotlib figures are rendered with the Agg backend so the suite is
  headless-safe.

Fixture overview
----------------
``repo_root``        absolute repository root
``config``           session-scoped :func:`acousticbench.config.load_config`
``data_path``        path to the real ``Data.mat`` (skips when absent)
``dataset``          session-scoped real dataset (no SHA-256, for speed)
``dataset_hashed``   real dataset including the SHA-256 fingerprint
``bands``            octave bands
``synthetic_suite``  small deterministic synthetic case suite (40 cases)
``small_mat_file``   valid synthetic MAT-file (documented schema, 2 NaN sessions)
``small_dataset``    session-scoped :class:`AcousticDataset` built from it
``h5_mat_file``      MATLAB v7.3 / HDF5 MAT-file for the loader fallback
``small_nan_sessions`` mapping of the planted NaN sessions
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Make matplotlib headless before any test imports pyplot via report/figures.
os.environ.setdefault("MPLCONFIGDIR", str(REPO_ROOT / ".cache" / "matplotlib"))
os.environ.setdefault("ACOUSTICBENCH_ROOT", str(REPO_ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

from acousticbench.types import (  # noqa: E402
    FREQUENCY_RESOLUTION_HZ,
    N_FREQUENCIES,
    N_REINSERTIONS,
    N_SUBJECTS,
    N_THRESHOLD_FREQUENCIES,
)

#: Audiometric frequencies of the dataset.
SMALL_THRESHOLD_FREQUENCIES = np.array([125, 250, 500, 750, 1000, 2000], dtype=np.uint16)

#: Planted all-NaN sessions of the synthetic MAT-fixture.
#:
#: Mapping ``container -> [(device_index, subject_index, reinsertion_index), ...]``
#: with 0-based indices.  Exactly two sessions are deliberately invalid so that
#: the measured-NaN handling of the loader / dataset can be tested without the
#: real data.  Only structurally *valid* device indices are used:
#:
#: * ``M_ha2edM`` device index 1 = code 2 = Closed Earmold · Measurement
#: * ``M_ha2edR`` device index 0 = code 1 = Closed Earmold · Reference
SMALL_NAN_SESSIONS: dict[str, tuple[tuple[int, int, int], ...]] = {
    "M_ha2edM": ((1, 2, 0),),
    "M_ha2edR": ((0, 4, 2),),
}

#: Complex containers of the dataset and their scale in the synthetic fixture.
_SMALL_FACTORS: dict[str, float] = {
    "M_ha2edM": 1.0,
    "M_ha2edR": 0.8,
    "M_ha2haf": 0.3,
    "M_ls2edM": 2.0,
    "M_ls2edR": 1.5,
}


def _small_variables() -> dict[str, np.ndarray]:
    """Build the variables of the synthetic, schema-valid MAT-file.

    The values are smooth deterministic functions of the four axes so that a
    test can verify aggregation / reshaping against direct array indexing.
    """
    frequency = np.arange(N_FREQUENCIES, dtype=float) * FREQUENCY_RESOLUTION_HZ
    amplitude = 1.0e-3 * (1.0 + 0.5 * np.sin(frequency / 1500.0))
    phase = 1.0e-3 * frequency
    base = amplitude * np.exp(1j * phase)  # (frequency,)

    device_scale = (1.0 + 0.05 * np.arange(1, 15))[None, :, None, None]
    subject_scale = (1.0 + 0.02 * np.arange(1, 15))[None, None, :, None]
    reinsertion_scale = (1.0 + 0.01 * np.arange(1, 4))[None, None, None, :]
    transfer = base[:, None, None, None] * device_scale * subject_scale * reinsertion_scale

    variables: dict[str, np.ndarray] = {}
    for key, factor in _SMALL_FACTORS.items():
        values = np.asarray(transfer * factor, dtype=np.complex128)
        for device, subject, reinsertion in SMALL_NAN_SESSIONS.get(key, ()):
            values[:, device, subject, reinsertion] = np.nan
        variables[key] = values

    threshold = (
        20.0
        + 3.0 * np.arange(N_THRESHOLD_FREQUENCIES)[:, None, None, None]
        + 0.5 * np.arange(1, N_SUBJECTS + 1)[None, :, None, None]
        + 0.1 * np.arange(1, N_REINSERTIONS + 1)[None, None, None, :]
    )
    variables["M_thr_ha"] = np.broadcast_to(threshold, (N_THRESHOLD_FREQUENCIES, 14, N_SUBJECTS, N_REINSERTIONS)).astype(float)
    variables["M_REUR"] = np.asarray(
        base[:, None] * (0.5 * (1.0 + 0.05 * np.arange(1, N_SUBJECTS + 1))[None, :]),
        dtype=np.complex128,
    )
    # The published file stores the axes as MATLAB row vectors (1, N).
    variables["v_frq"] = frequency.reshape(1, -1)
    variables["v_fAud"] = SMALL_THRESHOLD_FREQUENCIES.reshape(1, -1)
    return variables


def _write_small_mat(path: Path) -> Path:
    """Write the synthetic MAT-file (MATLAB v5, compressed)."""
    import scipy.io

    path.parent.mkdir(parents=True, exist_ok=True)
    scipy.io.savemat(path, _small_variables(), do_compression=True)
    return path


def _write_hdf5_mat(path: Path) -> Path:
    """Write a MATLAB v7.3 (HDF5) MAT-file.

    h5py writes the HDF5 signature at byte 512 (``userblock_size=512``); the
    128-byte MATLAB header in front of it makes :mod:`scipy.io` raise
    ``NotImplementedError`` and triggers the loader's h5py fallback.
    """
    import h5py

    path.parent.mkdir(parents=True, exist_ok=True)
    n_freq = N_FREQUENCIES
    n_dev, n_sub, n_re = 14, N_SUBJECTS, N_REINSERTIONS
    frequency = np.arange(n_freq, dtype=float) * FREQUENCY_RESOLUTION_HZ
    complex_type = np.dtype([("real", "<f8"), ("imag", "<f8")])

    def complex_container(factor: float) -> np.ndarray:
        # Deterministic values; gzip makes the (schema-mandated) array small.
        real = np.broadcast_to(
            (1.0e-3 * factor * (1.0 + 0.05 * np.arange(1, n_dev + 1))[None, :, None, None]),
            (n_re, n_sub, n_dev, n_freq),
        ).copy()
        values = np.zeros(real.shape, dtype=complex_type)
        values["real"] = real
        return values

    text = (
        b"MATLAB 7.3 MAT-file, Platform: PCWIN64, Created on: Mon Jan 01 "
        b"00:00:00 2026 HDF5 schema 0.5"
    )
    header = text + b" " * (116 - len(text)) + b"\x00" * 8 + b"\x00\x02IM"
    assert len(header) == 128

    with h5py.File(path, "w", userblock_size=512) as handle:
        handle.create_dataset(
            "v_frq", data=frequency.reshape(1, n_freq), compression="gzip"
        )
        handle.create_dataset(
            "v_fAud", data=SMALL_THRESHOLD_FREQUENCIES.reshape(1, -1)
        )
        for key, factor in _SMALL_FACTORS.items():
            handle.create_dataset(
                key, data=complex_container(factor), compression="gzip", compression_opts=4
            )
        handle.create_dataset(
            "M_thr_ha",
            data=np.broadcast_to(
                (20.0 + 3.0 * np.arange(N_THRESHOLD_FREQUENCIES)[None, None, None, :]),
                (n_re, n_sub, n_dev, N_THRESHOLD_FREQUENCIES),
            ).copy(),
            compression="gzip",
        )
        reur = np.zeros((n_sub, n_freq), dtype=complex_type)
        reur["real"] = np.broadcast_to(
            (5.0e-4 * (1.0 + 0.01 * np.arange(1, n_sub + 1)))[:, None],
            (n_sub, n_freq),
        )
        handle.create_dataset("M_REUR", data=reur, compression="gzip", compression_opts=4)
    with path.open("r+b") as handle:
        handle.seek(0)
        handle.write(header)
    return path


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute repository root of the checkout under test."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def config():
    """Session-scoped default configuration."""
    from acousticbench.config import load_config

    return load_config(root=REPO_ROOT)


@pytest.fixture(scope="session")
def data_path(config) -> Path:
    """Path to the real ``Data.mat``; skips the test when it is absent."""
    path = Path(config.data_path)
    if not path.is_file():
        pytest.skip(
            f"Real dataset not available at {path}; run scripts/fetch_data.py or set "
            "ACOUSTICBENCH_ROOT. This test is also marked requires_data."
        )
    return path


@pytest.fixture(scope="session")
def dataset(config, data_path):
    """Session-scoped real dataset without the (slow) SHA-256 fingerprint."""
    from acousticbench.data import load_dataset

    return load_dataset(data_path, config=config, compute_hash=False)


@pytest.fixture(scope="session")
def dataset_hashed(config, data_path):
    """Session-scoped real dataset including the SHA-256 provenance hash."""
    from acousticbench.data import load_dataset

    return load_dataset(data_path, config=config, compute_hash=True)


@pytest.fixture(scope="session")
def bands():
    """Octave bands used throughout the analyses."""
    from acousticbench.stats.bands import octave_bands

    return octave_bands()


@pytest.fixture(scope="session")
def synthetic_suite():
    """Small deterministic synthetic suite (40 cases, not rendered)."""
    from acousticbench.synthetic import build_cases

    return build_cases(n_cases=40)


@pytest.fixture(scope="session")
def _small_mat_template(tmp_path_factory) -> Path:
    """Session cache of the synthetic MAT-file (avoids re-writing 19 MB)."""
    directory = tmp_path_factory.mktemp("small_mat_template")
    return _write_small_mat(directory / "synthetic_schema.mat")


@pytest.fixture()
def small_mat_file(tmp_path, _small_mat_template) -> Path:
    """A valid synthetic MAT-file with the documented schema.

    The 19 MB session-cached template is copied so every test receives an
    isolated file.  Two sessions are deliberately all-NaN
    (see :data:`SMALL_NAN_SESSIONS`).
    """
    destination = tmp_path / "small_synthetic.mat"
    shutil.copyfile(_small_mat_template, destination)
    return destination


@pytest.fixture(scope="session")
def small_dataset(config, _small_mat_template):
    """Session-scoped :class:`AcousticDataset` built from the synthetic MAT-file."""
    from acousticbench.data import load_dataset

    return load_dataset(_small_mat_template, config=config, compute_hash=False)


@pytest.fixture()
def h5_mat_file(tmp_path) -> Path:
    """MATLAB v7.3 (HDF5) MAT-file for the ``h5py`` loader fallback."""
    pytest.importorskip("h5py", reason="h5py is required for the v7.3 fallback")
    return _write_hdf5_mat(tmp_path / "synthetic_v73.mat")


@pytest.fixture(scope="session")
def small_nan_sessions() -> dict[str, tuple[tuple[int, int, int], ...]]:
    """0-based ``(device, subject, reinsertion)`` indices of planted NaN sessions."""
    return {key: tuple(value) for key, value in SMALL_NAN_SESSIONS.items()}


@pytest.fixture(scope="session")
def small_fixture_sha256(_small_mat_template: Path) -> str:
    """SHA-256 of the synthetic MAT-file (computed independently with hashlib)."""
    digest = hashlib.sha256()
    with _small_mat_template.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Small helpers shared by tests (kept in conftest so they are importable)
# ---------------------------------------------------------------------------
def assert_close(actual: Any, desired: Any, *, rtol: float = 1e-10, atol: float = 1e-12) -> None:
    """Assert numeric closeness; convenience wrapper with project defaults."""
    np.testing.assert_allclose(np.asarray(actual), np.asarray(desired), rtol=rtol, atol=atol)
