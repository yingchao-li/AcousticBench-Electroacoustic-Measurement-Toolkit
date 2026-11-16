# Data: source, structure, units and validity

This document describes the measurement data used by AcousticBench, how it was
audited, and — most importantly — **which stored values are physically
meaningful**. Reproduce the audit with:

```bash
acb audit            # or: python scripts/run_experiments.sh --audit
```

Machine-readable results live in [`results/audit/`](../results/audit/):
`data_audit.json`, `data_audit.md`, `variables.csv`, `invalid_sessions.csv`,
`structural_validity.csv`, `checks.csv` and `data_audit_overview.png`.

---

## 1. Provenance

| | |
|---|---|
| Dataset | *Original data for: "On the effect of probe tube presence on measured hearing aid transmission behavior"* |
| Authors | Florian Denk, Lea Hackenberg, Hendrik Husstedt |
| DOI | [10.5281/zenodo.20023285](https://doi.org/10.5281/zenodo.20023285) |
| Licence | CC BY 4.0 |
| Files | `Data.mat` (MATLAB v5, ≈ 90 MB), `Documentation.pdf` |
| Publication | Preprint DOI [10.5281/zenodo.20023116](https://doi.org/10.5281/zenodo.20023116) |

The raw files are **not redistributed** in this repository (see
[`DATA_LICENSE.md`](../DATA_LICENSE.md)). Download them with:

```bash
python scripts/fetch_data.py      # verifies the SHA-256 of Data.mat
```

SHA-256 of the audited file:
`45cf5eeb83c659489a6dc981a59ae4fe045f2df2bbe6ebb084139dc3d5333e48`.

## 2. File structure

The MAT-file is a MATLAB v5 file containing frequency-domain results with
dimensions **frequency × device code × subject × reinsertion**. `M_REUR` is the
only 2-D container (frequency × subject).

| Variable | Shape | Type | Stored quantity | Unit |
|---|---|---|---|---|
| `v_frq` | (1, 2049) | float64 | frequency axis | Hz |
| `v_fAud` | (1, 6) | uint16 | audiometric frequencies | Hz |
| `M_ha2edM` | (2049, 14, 14, 3) | complex128 | HA driver → eardrum, measurement probe | Pa at 11.2 mV drive |
| `M_ha2edR` | (2049, 14, 14, 3) | complex128 | HA driver → eardrum, reference probe | Pa at 11.2 mV drive |
| `M_ha2haf` | (2049, 14, 14, 3) | complex128 | HA driver → HA microphone (feedback path) | Pa at 11.2 mV drive |
| `M_ls2edM` | (2049, 14, 14, 3) | complex128 | loudspeaker → eardrum, measurement probe | Pa at free-field reference |
| `M_ls2edR` | (2049, 14, 14, 3) | complex128 | loudspeaker → eardrum, reference probe | Pa at free-field reference |
| `M_thr_ha` | (6, 14, 14, 3) | float64 | hearing threshold (HA driver) | dBV at threshold |
| `M_REUR` | (2049, 14) | complex128 | real-ear unaided response, open ear | Pa at free-field reference |

### Axes

* **Frequency.** 2049 bins, 0 … 22 050 Hz, uniform Δf = 10.7666 Hz — the
  non-negative half of a **4096-point DFT at 44.1 kHz**. The excitation sweep
  covered 50 Hz … Nyquist; bins below 50 Hz carry no excitation and are excluded
  from every level statistic in the toolkit.
* **Device code (Dim 2).** 14 codes = seven earpiece families × two probe
  conditions. Odd codes are the *reference* condition, even codes the
  *measurement* condition:

  | Codes | Family | Coupling |
  |---|---|---|
  | 1 / 2 | Closed Earmold | earmold |
  | 3 / 4 | Vented Earmold | earmold |
  | 5 / 6 | Nugget Earmold | earmold |
  | 7 / 8 | Silicone Earmold | earmold |
  | 9 / 10 | Open Dome | dome |
  | 11 / 12 | Tulip Dome | dome |
  | 13 / 14 | Power Dome | dome |

* **Subject (Dim 3).** 1 … 14.
* **Reinsertion (Dim 4).** 1 … 3. Probe tubes stayed in place between
  reinsertions; the order of reference/measurement conditions was alternated and
  earpieces were balanced with a Latin square.

## 3. Units (and a subtlety)

### 3.1 Hearing-aid driver source

The stored complex pressures are **Pa at a receiver drive of 11.2 mV**. Two
conversions are physically meaningful and both are exposed by the toolkit:

| Quantity | Formula | Typical value (closed earmold, 1 kHz) |
|---|---|---|
| `Hha` in dB SPL at 11.2 mV | `20 log10(|p| / 20 µPa)` | **76.1 dB SPL** |
| `Hha` in dB re 1 Pa/V | `20 log10(|p| / 0.0112 V)` | 76.1 − 94.0 + 39.0 ≈ 21 dB |

The first is what Figure 4 of the source publication displays; the toolkit's
`hha_db_spl` and `hha_db_pa_per_v` implement both.

### 3.2 Loudspeaker source

The documentation states that loudspeaker-driven responses are "scaled as
pressure in Pa at free field". The audit shows that this does **not** mean
normalised to 1 Pa: the loosely hanging measurement probe in the reference
condition — a direct in-situ free-field probe — reads ≈ **−27 dB** at 1 kHz,
and the open-ear REUR is ≈ −26 dB. Consequently:

* **ratios are calibrated** and scale-invariant: REOIG, insertion gain and all
  cross-probe comparisons are unaffected;
* **absolute levels** need a free-field reference. AcousticBench derives an
  **in-situ free-field reference** from the documented loose measurement probe
  in the reference condition (median over the seven reference-condition
  earpieces). The resulting real-ear unaided gain is +0.6 dB at 1 kHz,
  +14.0 dB at 2 kHz and +15.7 dB at 4 kHz — the expected ear-canal resonance,
  which validates the normalisation.

The audit records this as an explicit, non-blocking caveat
(`absolute_free_field_scaling`). Do not interpret raw `M_ls*` dB values as
dB SPL re 20 µPa without the in-situ reference.

### 3.3 Thresholds

`M_thr_ha` is the **receiver voltage at threshold in dBV** at 125, 250, 500,
750, 1000, 2000 Hz. Values are quantised to 1 dB (maximum observed residual
0.0 dB), which limits the resolution of threshold-based effect estimates.

## 4. Missing values: two different kinds of "invalid"

AcousticBench never imputes. It distinguishes:

### 4.1 Measured NaNs (erroneous measurements)

Exactly **18 complete (device, subject, reinsertion) sessions** are NaN in all
five 4-D transfer-function containers. The NaN mask is *identical* across the
five containers — a failed measurement session is invalidated as a whole. The
threshold container has **19** completely invalid sessions: the same 18 plus one
additional threshold-only session (power dome, subject 3, reinsertion 2). No
partial/ragged NaN columns exist.

The 18 invalid sessions are listed in
[`results/audit/invalid_sessions.csv`](../results/audit/invalid_sessions.csv).

### 4.2 Structural invalidity (numbers that exist but are not the intended quantity)

Documentation and the preprint define the probe conditions precisely:

* In the **reference condition** only the reference probe tube is in the ear for
  earmolds. The **measurement probe microphone was hanging loosely around the
  ear** — its signal is not an eardrum pressure, although it is stored as a
  number.
* The **reference probe tube was only used for earmolds** (routed through a
  dedicated bore in the earmold). For domes there is no reference-probe eardrum
  pressure at all.
* The measurement-probe loudspeaker responses in the reference condition, and
  the reference-probe loudspeaker responses for domes, are free-field-ish
  signals, not eardrum pressures.

This yields the following validity matrix (enforced in
`src/acousticbench/types.py` and used by every analysis):

| Container | Valid conditions | Valid couplings | Structural rule |
|---|---|---|---|
| `M_ha2edM` | measurement | all | MPT loose in reference condition |
| `M_ha2edR` | both | earmold | RPT not used with domes |
| `M_ha2haf` | both | all | HA microphone always in place |
| `M_ls2edM` | measurement | all | MPT loose in reference condition |
| `M_ls2edR` | both | earmold | RPT not used with domes |
| `M_thr_ha` | both | all | behavioural thresholds always meaningful |
| `M_REUR` | open ear | — | one insertion, measurement probe |

The audit confirms these rules **empirically** from the data rather than
trusting the text blindly:

| Signature | Observed | Expected |
|---|---|---|
| MPT level, reference vs in-ear (1 kHz) | 44.9–62.4 dB lower | ≫ 20 dB |
| RPT level, earmold vs dome (1 kHz) | 59.2 dB lower for domes | ≫ 20 dB |
| Across-device SD of loose MPT (loudspeaker) | 0.52 dB at 1 kHz | < 2 dB (free field) |
| Across-device SD of loose RPT for domes | 0.34 dB at 1 kHz | < 2 dB (free field) |
| Cross-probe agreement, both in ear (0.5–4 kHz) | median 1.7 dB, MPT ≈ 1.5 dB lower | few dB |
| REOIG at 1 kHz, closed earmold / open dome | −10.9 dB / +0.5 dB | negative / ≈ 0 |
| In-situ REUG at 1/2/4 kHz | +0.6 / +14.0 / +15.7 dB | ear-canal resonance |
| ΔHha at 100 Hz (probe insertion) | −4.4 dB median | negative |
| ΔREOIG at 2 kHz | +1.4 dB median | positive |
| ΔT at 125 Hz | −2.0 dB median | negative |

The validity rules are encoded in `ContainerSpec` and surfaced by
`AcousticDataset.structural_mask()`, `TransferCube.valid` and
`invalid_sessions()`. A derived quantity that needs a structurally invalid
entry (the in-situ free-field reference) says so explicitly in its docstring.

## 5. Data-quality findings (summary)

* Schema, shapes, dtypes and axes match the documentation exactly.
* Uniform DFT grid confirmed; DC and < 50 Hz bins excluded from level statistics.
* 18 invalid transfer-function sessions (3.06 % of 588 sessions) and 19 invalid
  threshold sessions; whole-session invalidation only.
* Threshold quantisation = 1 dB.
* Within-subject reinsertion SD of Hha (0.5–4 kHz, measurement condition):
  **median 0.38 dB, 95th percentile 1.47 dB** — the noise floor for
  probe-presence effects.
* Probe-to-probe bias in the measurement condition: MPT reads ≈ 1.4–1.7 dB
  lower than RPT between 100 Hz and 4 kHz (≈ 3.1 dB at 8 kHz). This is a real
  placement/calibration bias, not noise; it is reported, not removed.
* The probe-tube presence effect is reproduced with the expected signs
  (ΔHha < 0, ΔREOIG > 0, ΔT < 0), including the strong low-frequency effect of
  the nugget earmold (−8.6 dB at ~100 Hz).
* The loudspeaker-source absolute scaling is not normalised to 1 Pa free field;
  use ratios or the in-situ reference (documented caveat).

## 6. Loading the data in code

```python
from acousticbench.data import load_dataset

ds = load_dataset()                 # uses config.paths.data_mat
print(ds.describe())
cube = ds.get("M_ha2edR", conditions=["measurement"], couplings=["earmold"])
print(cube.valid.mean())            # validity mask already applied
level = cube.magnitude_db(reference=20e-6)   # dB SPL at 11.2 mV
```

High-level measurement functions (`acousticbench.measurements`) apply the
validity rules automatically; for example `hha_db_spl(ds, probe="measurement",
condition="reference")` raises `MeasurementError` instead of returning the
loose-probe signal.

## 7. Interpretation limits

See [`limitations.md`](limitations.md) for the full list. The most important
ones:

* This is a secondary analysis of one open dataset (14 ears, one ear per
  participant), not a clinical validation.
* Loose-probe and missing-reference-probe values are excluded by design; the
  resulting reference-condition sample is smaller.
* The absolute free-field normalisation is *inferred* (in-situ proxy), not
  provided by the dataset.
* Probe positioning, insertion depth and high-frequency standing waves are not
  modelled; the > 8 kHz region carries larger probe-related uncertainty.
* Synthetic validation establishes algorithmic accuracy only under the
  documented reference conditions; it does not validate the physical dataset.
