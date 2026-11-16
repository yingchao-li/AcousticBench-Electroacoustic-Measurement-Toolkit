"""Data loading, validity and auditing."""

from acousticbench.data.dataset import AcousticDataset, TransferCube, load_dataset
from acousticbench.data.units import (
    db_to_amplitude,
    db_to_pa,
    magnitude_db,
    pa_to_db_pa_per_v,
    pa_to_db_spl,
    phase_deg,
)
from acousticbench.data.validity import (
    build_valid_mask,
    invalid_reasons_table,
    invalid_sessions,
    structural_validity,
    structural_validity_table,
)

__all__ = [
    "AcousticDataset",
    "TransferCube",
    "load_dataset",
    "build_valid_mask",
    "invalid_reasons_table",
    "invalid_sessions",
    "structural_validity",
    "structural_validity_table",
    "db_to_amplitude",
    "db_to_pa",
    "magnitude_db",
    "pa_to_db_pa_per_v",
    "pa_to_db_spl",
    "phase_deg",
]
