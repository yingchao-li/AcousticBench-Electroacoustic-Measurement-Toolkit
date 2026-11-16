"""Statistics: descriptive, paired inference, bootstrap, correction and ICC.

The subject is the independent statistical unit: reinsertions are technical
repeats and must be collapsed within subject before any inferential test (use
:func:`acousticbench.stats.descriptive.subject_means`).
"""

from acousticbench.stats.bands import (
    Band,
    bands_from_config,
    custom_bands,
    octave_bands,
    third_octave_bands,
)
from acousticbench.stats.bootstrap import (
    BootstrapResult,
    bootstrap_ci,
    bootstrap_paired_ci,
    cluster_bootstrap_ci,
)
from acousticbench.stats.correction import (
    benjamini_hochberg,
    holm_bonferroni,
    reject,
)
from acousticbench.stats.descriptive import describe_array, subject_means, summarize_layout
from acousticbench.stats.effect_size import cohen_d, cohen_dz, hedges_g, rank_biserial
from acousticbench.stats.icc import IccResult, icc_2_1
from acousticbench.stats.paired import (
    PairedTestResult,
    normality_check,
    paired_summary,
    paired_t_test,
    wilcoxon_signed_rank,
)

__all__ = [
    "Band",
    "BootstrapResult",
    "IccResult",
    "PairedTestResult",
    "bands_from_config",
    "benjamini_hochberg",
    "bootstrap_ci",
    "bootstrap_paired_ci",
    "cluster_bootstrap_ci",
    "cohen_d",
    "cohen_dz",
    "custom_bands",
    "describe_array",
    "hedges_g",
    "holm_bonferroni",
    "icc_2_1",
    "normality_check",
    "octave_bands",
    "paired_summary",
    "paired_t_test",
    "rank_biserial",
    "reject",
    "subject_means",
    "summarize_layout",
    "third_octave_bands",
    "wilcoxon_signed_rank",
]
