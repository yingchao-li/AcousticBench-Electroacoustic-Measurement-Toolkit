"""Exception hierarchy used throughout AcousticBench.

All toolkit-specific errors derive from :class:`AcousticBenchError`, so that
applications (CLI, dashboard, experiment runner) can catch a single base class
without swallowing unrelated programming errors.
"""

from __future__ import annotations


class AcousticBenchError(Exception):
    """Base class for all AcousticBench errors."""


class ConfigurationError(AcousticBenchError):
    """Raised when a configuration file is missing, malformed or inconsistent."""


class DataValidationError(AcousticBenchError):
    """Raised when input data does not match the expected schema.

    This covers missing variables, wrong array shapes/dtypes, non-monotonic
    frequency axes and physically impossible values.  It never covers
    *measured* NaN entries: those are part of the documented dataset.
    """


class DataSelectionError(AcousticBenchError):
    """Raised when a selection yields no analysable data."""


class UnitError(AcousticBenchError):
    """Raised on an incompatible unit conversion."""


class MeasurementError(AcousticBenchError):
    """Raised when a physical quantity cannot be computed from the data."""


class InsufficientDataError(MeasurementError):
    """Raised when too few valid subjects/reinsertions exist for an estimate."""


class SyntheticCaseError(AcousticBenchError):
    """Raised when a synthetic test case is malformed or out of range."""


class ExperimentError(AcousticBenchError):
    """Raised when an experiment fails to execute."""


class MatlabNotAvailableError(AcousticBenchError):
    """Raised when MATLAB-specific functionality is requested without MATLAB."""


class ReportError(AcousticBenchError):
    """Raised when report generation fails."""


class ValidationError(AcousticBenchError):
    """Raised when a validation tolerance is violated in a strict check."""
