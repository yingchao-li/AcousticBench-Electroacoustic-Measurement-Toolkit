#!/usr/bin/env python3
"""Download and verify the published AcousticBench dataset from Zenodo.

The measurement data is **not** redistributed with this repository.  This
script downloads the two published files, verifies the SHA-256 of ``Data.mat``
against the pinned value from ``DATA_LICENSE.md`` and prints the hash of
``Documentation.pdf`` (no pinned hash is published for the PDF, so it is
recorded for provenance only).

Usage
-----
    python scripts/fetch_data.py                 # download missing files
    python scripts/fetch_data.py --force         # re-download everything
    python scripts/fetch_data.py --output-dir data/raw

Exit codes
----------
0   files present and verified (downloaded or already up to date)
1   network/IO error or SHA-256 mismatch
2   invalid command line usage
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

DATA_URL = "https://zenodo.org/records/20023285/files/Data.mat?download=1"
DOCUMENTATION_URL = "https://zenodo.org/records/20023285/files/Documentation.pdf?download=1"

#: Pinned SHA-256 of the published Data.mat (see DATA_LICENSE.md).
DATA_SHA256 = "45cf5eeb83c659489a6dc981a59ae4fe045f2df2bbe6ebb084139dc3d5333e48"

REPO_ROOT = Path(__file__).resolve().parents[1]
_USER_AGENT = "AcousticBench-fetch_data/1.0 (+https://doi.org/10.5281/zenodo.20023285)"


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _download_urllib(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - fixed URL
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle, length=1 << 20)


def _download_requests(url: str, destination: Path) -> None:
    import requests  # type: ignore[import-not-found]

    response = requests.get(url, stream=True, timeout=120, headers={"User-Agent": _USER_AGENT})
    response.raise_for_status()
    with destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1 << 20):
            if chunk:
                handle.write(chunk)


def download(url: str, destination: Path) -> None:
    """Download ``url`` to ``destination`` (atomic via a temporary file).

    Tries the standard library first and falls back to ``requests`` when
    available; clear errors are raised on network failure.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    try:
        try:
            _download_urllib(url, partial)
        except Exception as urllib_error:  # noqa: BLE001 - fall back to requests
            try:
                _download_requests(url, partial)
            except ImportError:
                raise urllib_error
            except Exception as requests_error:  # noqa: BLE001
                raise RuntimeError(
                    f"download failed for {url}: {urllib_error} / {requests_error}"
                ) from requests_error
        if not partial.is_file() or partial.stat().st_size == 0:
            raise RuntimeError(f"download of {url} produced an empty file")
        os.replace(partial, destination)
    finally:
        if partial.exists():
            partial.unlink()


def _describe(path: Path) -> str:
    return f"{path.name} ({path.stat().st_size / 1024**2:.1f} MiB, sha256={sha256_of(path)})"


def fetch(
    output_dir: Path = REPO_ROOT,
    *,
    force: bool = False,
) -> dict[str, str]:
    """Fetch and verify the dataset files; return their SHA-256 digests."""
    data_path = output_dir / "Data.mat"
    pdf_path = output_dir / "Documentation.pdf"
    digests: dict[str, str] = {}

    if data_path.is_file() and not force:
        digest = sha256_of(data_path)
        if digest == DATA_SHA256:
            size_mib = data_path.stat().st_size / 1024**2
            print(
                f"[skip] Data.mat already present and verified "
                f"({data_path.name}, {size_mib:.1f} MiB, sha256={digest})"
            )
            digests["Data.mat"] = digest
        else:
            raise RuntimeError(
                f"Existing {data_path} has SHA-256 {digest}, expected {DATA_SHA256}. "
                "Use --force to re-download it."
            )
    else:
        print(f"[download] {DATA_URL}")
        download(DATA_URL, data_path)
        digest = sha256_of(data_path)
        if digest != DATA_SHA256:
            data_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"SHA-256 mismatch for downloaded Data.mat: got {digest}, "
                f"expected {DATA_SHA256}. The file was removed."
            )
        digests["Data.mat"] = digest
        print(f"[ok] Data.mat verified ({_describe(data_path)})")

    if pdf_path.is_file() and not force:
        digest = sha256_of(pdf_path)
        print(
            f"[skip] Documentation.pdf already present "
            f"({pdf_path.name}, sha256={digest})"
        )
        digests["Documentation.pdf"] = digest
    else:
        print(f"[download] {DOCUMENTATION_URL}")
        download(DOCUMENTATION_URL, pdf_path)
        digest = sha256_of(pdf_path)
        digests["Documentation.pdf"] = digest
        print(
            f"[ok] Documentation.pdf downloaded ({_describe(pdf_path)}); "
            "no pinned SHA-256 is published for the PDF."
        )

    print("")
    print("Dataset ready. Citation (see DATA_LICENSE.md):")
    print("  Denk, Hackenberg & Husstedt (2026), doi:10.5281/zenodo.20023285, CC BY 4.0")
    return digests


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch_data.py",
        description=(
            "Download Data.mat and Documentation.pdf from Zenodo and verify the "
            "SHA-256 of Data.mat."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT,
        help="Directory where the files are written (default: repository root)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even when a verified file already exists",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir).expanduser().resolve()
    try:
        fetch(output_dir, force=bool(args.force))
    except (RuntimeError, OSError, urllib.error.URLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
