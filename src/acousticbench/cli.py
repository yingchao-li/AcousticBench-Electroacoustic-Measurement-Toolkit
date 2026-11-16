"""Command-line interface for AcousticBench.

Usage examples
--------------
    acb inspect                     # inspect Data.mat and print the schema
    acb audit                       # full data-quality audit
    acb experiments                 # run all 16 experiments
    acb experiments --codes E01 E02 # run selected experiments
    acb report                      # build PDF/Excel/HTML reports
    acb validate                    # MATLAB/Python cross-language check (E15)
    acb dashboard --port 8501       # launch the Streamlit dashboard
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from acousticbench import __version__
from acousticbench.config import Config, load_config, repo_root
from acousticbench.exceptions import AcousticBenchError
from acousticbench.logging_utils import get_logger, setup_logging

__all__ = ["build_parser", "main"]

_LOG = get_logger("cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="acb",
        description=(
            "AcousticBench — electroacoustic measurement, validation and reporting toolkit"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional user YAML configuration merged over config/default.yaml",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override the configured log level (DEBUG, INFO, WARNING, ERROR)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser("inspect", help="Inspect and validate Data.mat")
    inspect.add_argument("--data", type=Path, default=None, help="Path to Data.mat")
    inspect.add_argument("--json", action="store_true", help="Print the summary as JSON")

    audit = subparsers.add_parser("audit", help="Run the data-quality audit")
    audit.add_argument("--data", type=Path, default=None, help="Path to Data.mat")
    audit.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: results/audit)",
    )
    audit.add_argument("--no-figure", action="store_true", help="Skip the audit figure")

    experiments = subparsers.add_parser("experiments", help="Run reproducible experiments")
    experiments.add_argument(
        "--codes",
        nargs="+",
        default=None,
        help="Experiment codes to run (default: all enabled in the configuration)",
    )
    experiments.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output root (default: results/experiments)",
    )
    experiments.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any experiment fails",
    )

    report = subparsers.add_parser("report", help="Build PDF/Excel/HTML reports")
    report.add_argument("--results", type=Path, default=None, help="Results root directory")
    report.add_argument(
        "--output", type=Path, default=None, help="Report output directory (default: reports)"
    )
    report.add_argument(
        "--formats",
        nargs="+",
        default=["pdf", "excel", "html"],
        choices=["pdf", "excel", "html"],
        help="Report formats to build",
    )

    validate = subparsers.add_parser("validate", help="Run the cross-language validation")
    validate.add_argument("--output", type=Path, default=None, help="Output directory")
    validate.add_argument("--json", action="store_true", help="Print the report as JSON")

    dashboard = subparsers.add_parser("dashboard", help="Launch the Streamlit dashboard")
    dashboard.add_argument("--port", type=int, default=8501, help="TCP port")
    dashboard.add_argument(
        "--headless", action="store_true", help="Run Streamlit without opening a browser"
    )

    return parser


def _dataset_from_args(config: Config, args: argparse.Namespace):
    from acousticbench.data import load_dataset

    path = getattr(args, "data", None) or config.data_path
    return load_dataset(path, config=config)


def _command_inspect(config: Config, args: argparse.Namespace) -> int:
    from acousticbench.io import inspect_mat

    path = args.data or config.data_path
    summary = inspect_mat(path)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        info = summary["file"]
        print(f"File      : {info['path']}")
        print(f"Size      : {info['size_mb']} MB")
        print(f"MAT format: {info['mat_format']}")
        print(f"SHA-256   : {info['sha256']}")
        print(f"Header    : {info['header']}")
        print("\nVariables:")
        for name, entry in summary["variables"].items():
            print(
                f"  {name:10s} shape={str(entry['shape']):20s} "
                f"dtype={entry['dtype']:12s} complex={entry['complex']}"
            )
        if summary["warnings"]:
            print("\nWarnings:")
            for warning in summary["warnings"]:
                print(f"  - {warning}")
    return 0


def _command_audit(config: Config, args: argparse.Namespace) -> int:
    dataset = _dataset_from_args(config, args)
    output = args.output or config.results_dir / "audit"
    audit = dataset.audit()
    paths = audit.save(output, make_figure=not args.no_figure)
    print(
        f"Audit complete: {len(audit.findings)} checks, "
        f"{audit.n_errors} errors, {audit.n_warnings} warnings."
    )
    for name, path in paths.items():
        print(f"  {name:12s} {path}")
    return 0 if audit.n_errors == 0 else 1


def _command_experiments(config: Config, args: argparse.Namespace) -> int:
    from acousticbench.experiments import ExperimentRunner

    dataset = _dataset_from_args(config, args)
    runner = ExperimentRunner(config, output_root=args.output)
    results = runner.run_all(args.codes, dataset=dataset)
    print("\nExperiment summary")
    print("------------------")
    failed = 0
    for result in results:
        status = result.status
        failed += int(status != "completed")
        print(
            f"  {result.code}  {status:9s}  {result.duration_s:7.2f} s  "
            f"{len(result.artifacts.get('tables', []))} tables / "
            f"{len(result.artifacts.get('figures', []))} figures"
        )
    print(f"\nArtefacts: {config.results_dir / 'experiments'}")
    if args.strict and failed:
        return 1
    return 0


def _command_report(config: Config, args: argparse.Namespace) -> int:
    try:
        from acousticbench.report.builder import build_all_reports, load_saved_results
    except ImportError as exc:  # pragma: no cover - reporting layer optional at CLI start
        raise AcousticBenchError(f"Reporting layer is not available: {exc}") from exc

    results_root = args.results or config.results_dir / "experiments"
    results = load_saved_results(results_root, config)
    if not results:
        raise AcousticBenchError(
            f"No saved experiments found under {results_root}; run `acb experiments` first."
        )
    from acousticbench.report.builder import load_saved_audit

    audit = load_saved_audit(config.results_dir)
    output = args.output or config.reports_dir
    paths = build_all_reports(
        results,
        output,
        config=config,
        audit=audit,
        formats=tuple(args.formats),
    )
    print("Reports generated:")
    for fmt, path in paths.items():
        print(f"  {fmt:6s} {path}")
    return 0


def _command_validate(config: Config, args: argparse.Namespace) -> int:
    from acousticbench.validation.cross_language import run_cross_language_validation

    dataset = _dataset_from_args(config, args)
    output = args.output or config.results_dir / "validation"
    report = run_cross_language_validation(dataset, config, output)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"MATLAB available : {report.matlab_available}")
        print(f"MATLAB status    : {report.matlab_status}")
        if report.matlab_error:
            print(f"Reason           : {report.matlab_error}")
        print("Port-vs-production agreement:")
        for comparison in report.port_comparisons:
            print(
                f"  {comparison.name:45s} n={comparison.n:4d} "
                f"max|Δ|={comparison.max_abs_diff:.3e} {comparison.unit} "
                f"tolerance={comparison.tolerance:g} -> {'PASS' if comparison.passed else 'FAIL'}"
            )
        for comparison in report.matlab_comparisons:
            print(
                f"  MATLAB {comparison.name:38s} n={comparison.n:4d} "
                f"max|Δ|={comparison.max_abs_diff:.3e} {comparison.unit} "
                f"-> {'PASS' if comparison.passed else 'FAIL'}"
            )
    return 0 if report.port_agreement_passed else 1


def _command_dashboard(config: Config, args: argparse.Namespace) -> int:
    app_path = repo_root() / "app" / "dashboard.py"
    if not app_path.is_file():
        raise AcousticBenchError(f"Dashboard entrypoint not found: {app_path}")
    environment = dict(os.environ)
    source_dir = str(repo_root() / "src")
    environment["PYTHONPATH"] = (
        source_dir
        if not environment.get("PYTHONPATH")
        else source_dir + os.pathsep + environment["PYTHONPATH"]
    )
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(args.port),
    ]
    if args.headless:
        command.extend(["--server.headless", "true"])
    print("Launching:", " ".join(command))
    try:
        return subprocess.call(command, env=environment)
    except KeyboardInterrupt:  # pragma: no cover - interactive
        return 0


_DISPATCH = {
    "inspect": _command_inspect,
    "audit": _command_audit,
    "experiments": _command_experiments,
    "report": _command_report,
    "validate": _command_validate,
    "dashboard": _command_dashboard,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``acb`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except AcousticBenchError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    level = args.log_level or config.logging.level
    setup_logging(level, config.log_file, force=True)
    _LOG.debug("Command: %s", args.command)
    try:
        return int(_DISPATCH[args.command](config, args))
    except AcousticBenchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        _LOG.error("%s", exc)
        return 2
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
