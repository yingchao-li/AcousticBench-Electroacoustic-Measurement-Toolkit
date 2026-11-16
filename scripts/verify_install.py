#!/usr/bin/env python3
"""AcousticBench installation verification.

Checks the Python environment, the optional runtime dependencies, the
configuration, a tiny synthetic DSP smoke test and — when present — the
SHA-256 of the published ``Data.mat``.  Prints a PASS/FAIL checklist and exits
non-zero if anything failed.

Usage
-----
    python scripts/verify_install.py [--skip-data] [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DATA_SHA256 = "45cf5eeb83c659489a6dc981a59ae4fe045f2df2bbe6ebb084139dc3d5333e48"

#: (module, distribution, required) — required deps come from pyproject.toml.
_DEPENDENCIES: tuple[tuple[str, str, bool], ...] = (
    ("numpy", "numpy", True),
    ("scipy", "scipy", True),
    ("pandas", "pandas", True),
    ("h5py", "h5py", True),
    ("yaml", "PyYAML", True),
    ("matplotlib", "matplotlib", True),
    ("plotly", "plotly", True),
    ("streamlit", "streamlit", True),
    ("jinja2", "jinja2", True),
    ("reportlab", "reportlab", True),
    ("openpyxl", "openpyxl", True),
    ("xlsxwriter", "xlsxwriter", True),
    ("pytest", "pytest", False),
    ("pytest_cov", "pytest-cov", False),
    ("pypdf", "pypdf", False),
    ("pymupdf", "pymupdf", False),
)


class Checklist:
    """Collect PASS/FAIL/SKIP lines and the corresponding exit code."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []
        self.failed = 0

    def record(self, status: str, name: str, detail: str = "") -> None:
        self.rows.append((status, name, detail))
        if status == "FAIL":
            self.failed += 1
        mark = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
        line = f"{mark} {name}"
        if detail:
            line += f" — {detail}"
        print(line)

    def finish(self) -> int:
        passed = sum(1 for status, _, _ in self.rows if status == "PASS")
        skipped = sum(1 for status, _, _ in self.rows if status == "SKIP")
        print("")
        print(
            f"Result: {passed} passed, {self.failed} failed, {skipped} skipped "
            f"(Python {platform.python_version()}, {platform.platform()})"
        )
        if self.failed:
            print("Installation verification FAILED.")
            return 1
        print("Installation verification PASSED.")
        return 0


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def check_python(checklist: Checklist) -> None:
    version = sys.version_info
    if version >= (3, 10):
        checklist.record("PASS", "Python >= 3.10", f"{platform.python_version()}")
    else:
        checklist.record("FAIL", "Python >= 3.10", f"found {platform.python_version()}")


def check_dependencies(checklist: Checklist) -> None:
    for module_name, distribution, required in _DEPENDENCIES:
        kind = "required dependency" if required else "dev dependency"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - report any import failure
            if required:
                checklist.record("FAIL", f"{distribution} import", repr(exc))
            else:
                checklist.record("SKIP", f"{distribution} import (optional)", repr(exc))
            continue
        version = getattr(module, "__version__", "")
        if not version:
            try:
                from importlib import metadata

                version = metadata.version(distribution)
            except Exception:  # noqa: BLE001 - version is informational only
                version = "unknown"
        checklist.record("PASS", f"{distribution} import", f"{kind}, version {version}")


def check_package(checklist: Checklist) -> bool:
    try:
        import acousticbench
        from acousticbench.config import load_config
        from acousticbench.data import AcousticDataset  # noqa: F401
        from acousticbench.experiments import ExperimentRunner  # noqa: F401
        from acousticbench.io import load_mat  # noqa: F401
        from acousticbench.measurements import hha_db_spl  # noqa: F401
        from acousticbench.stats.bands import octave_bands  # noqa: F401

        config = load_config()
        assert config.project.name == "AcousticBench"
        assert config.root.is_dir()
        checklist.record(
            "PASS", "acousticbench import + configuration", f"version {acousticbench.__version__}"
        )
        return True
    except Exception as exc:  # noqa: BLE001 - report any failure
        checklist.record("FAIL", "acousticbench import + configuration", repr(exc))
        return False


def check_synthetic_smoke(checklist: Checklist) -> None:
    try:
        from acousticbench.dsp.metrics import estimate_gain_db
        from acousticbench.synthetic import build_cases, render_case

        cases = build_cases(n_cases=5, seed=20260422)
        assert len(cases) == 5
        gain_cases = [case for case in cases if case.category == "gain"]
        if not gain_cases:
            checklist.record("SKIP", "synthetic case smoke test", "no gain case in the tiny suite")
            return
        data = render_case(gain_cases[0])
        estimate = estimate_gain_db(
            data.input, data.output, data.fs_hz, tone_hz=float(data.ground_truth["tone_hz"])
        )
        error = estimate.gain_db - float(data.ground_truth["gain_db"])
        if abs(error) <= 0.1:
            checklist.record(
                "PASS", "synthetic case + gain estimator", f"error {error:+.4f} dB (target 0.1 dB)"
            )
        else:
            checklist.record(
                "FAIL", "synthetic case + gain estimator", f"error {error:+.4f} dB > 0.1 dB"
            )
    except Exception as exc:  # noqa: BLE001 - report any failure
        checklist.record("FAIL", "synthetic case + gain estimator", repr(exc))


def check_dataset(checklist: Checklist, *, skip_data: bool) -> None:
    data_path = REPO_ROOT / "Data.mat"
    if skip_data:
        checklist.record("SKIP", "Data.mat presence + SHA-256", "--skip-data requested")
        return
    if not data_path.is_file():
        checklist.record(
            "SKIP",
            "Data.mat presence + SHA-256",
            "not downloaded; run '.venv/bin/python scripts/fetch_data.py'",
        )
        return
    try:
        digest = sha256_of(data_path)
    except OSError as exc:
        checklist.record("FAIL", "Data.mat presence + SHA-256", repr(exc))
        return
    if digest == EXPECTED_DATA_SHA256:
        size_mib = data_path.stat().st_size / 1024**2
        checklist.record(
            "PASS", "Data.mat presence + SHA-256", f"{size_mib:.1f} MiB, hash matches"
        )
    else:
        checklist.record(
            "FAIL",
            "Data.mat presence + SHA-256",
            f"got {digest}, expected {EXPECTED_DATA_SHA256}",
        )
    pdf_path = REPO_ROOT / "Documentation.pdf"
    if pdf_path.is_file():
        checklist.record("PASS", "Documentation.pdf presence", f"{pdf_path.stat().st_size} bytes")
    else:
        checklist.record(
            "SKIP", "Documentation.pdf presence", "not downloaded (optional for analysis)"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_install.py",
        description="Verify the AcousticBench installation, configuration and dataset.",
    )
    parser.add_argument(
        "--skip-data", action="store_true", help="Skip the Data.mat presence/SHA-256 check"
    )
    parser.add_argument("--json", action="store_true", help="Also print the checklist as JSON")
    args = parser.parse_args(argv)

    print("AcousticBench installation verification")
    print("=" * 60)
    checklist = Checklist()
    check_python(checklist)
    check_dependencies(checklist)
    if check_package(checklist):
        check_synthetic_smoke(checklist)
    check_dataset(checklist, skip_data=bool(args.skip_data))
    exit_code = checklist.finish()

    if args.json:
        print(
            json.dumps(
                [
                    {"status": status, "check": name, "detail": detail}
                    for status, name, detail in checklist.rows
                ],
                indent=2,
            )
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
