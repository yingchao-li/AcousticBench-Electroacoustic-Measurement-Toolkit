# AcousticBench MATLAB toolkit (independent implementation)

Independent MATLAB reference implementation of the AcousticBench dataset
semantics, measurement metrics, DSP algorithms, statistics, synthetic cases,
cross-language export (experiment E15) and a programmatic GUI.

Status: **authored but NOT EXECUTED / NOT VERIFIED**. MATLAB is not installed
in the authoring environment and the GNU Octave installation attempt failed
(Homebrew `/opt/homebrew` not writable), so no MATLAB/Octave run, no test
result, no GUI screenshot and no numerical MATLAB output exist. See the
verification-status section below and `docs/matlab_status.md`. Nothing in
this directory may be cited as a passing test run.

The Python package under `src/acousticbench/` is the primary implementation.
This MATLAB tree is the *independent cross-language reference*: E15 compares
the numbers produced here with the Python results, and a disagreement is a
finding, not something to hide.

## Requirements

- MATLAB R2021b or later.
- Base MATLAB only. **No toolbox is required or used**: no `pwelch`,
  `butter`, `filtfilt`, `tf2sos`, `tinv`, `prctile`, `hilbert`, `resample`
  or similar Signal Processing / Statistics Toolbox calls. Windowing,
  windowed-sinc FIR design, Butterworth design via the bilinear transform,
  zero-phase filtering, Welch PSD/CSF, Student-t quantiles, bootstrap
  percentiles and the signed-rank test are implemented from scratch.
- `Data.mat` (MATLAB v5, the published dataset of Denk, Hackenberg &
  Husstedt 2026, doi:10.5281/zenodo.20023285) at the repository root for the
  dataset functions and the cross-language export.
- A MATLAB desktop session for the GUI (`uifigure`/`uiaxes`). The automated
  GUI tests assume `usejava('desktop')` and are skipped otherwise.

## Layout

```
matlab/
  README.md                          this file
  run_cross_language_export.m        E15: Data.mat + matlab_inputs.mat -> matlab_reference.csv
  +acousticbench/                    namespace package (dataset + measurements)
    constants.m                      physical/dataset constants
    deviceTable.m                    14 device/condition codes (7 families x ref/meas)
    loadData.m                       load + validate Data.mat, validity masks
    structuralValidityTable.m        98-row container x device validity table
    hha.m                            HA driver -> eardrum response [dB SPL | dB re Pa/V]
    reoig.m                          real-ear occluded insertion gain [dB]
    ptpe.m                           probe-tube presence effect (hha | reoig | threshold)
    feedbackPath.m                   HA driver -> HA microphone path [dB]
    thresholdTable.m                 tidy threshold table [dBV]
    bandLevels.m                     power-averaged band levels from dB data
    octaveBands.m                    octave-band struct array (IEC 61260 centres)
    thirdOctaveBands.m               one-third-octave-band struct array
    referenceMetrics.m               the E15 dataset reference rows (142 rows)
    +dsp/                            independent DSP (no toolbox)
      windowVector.m                 rect/hann/hamming/blackman windows
      fftSpectrum.m                  single-sided amplitude spectrum
      stftSpectrum.m                 short-time Fourier transform
      welchPsd.m                     Welch PSD
      designFir.m                    windowed-sinc FIR (low/high/bandpass)
      designIir.m                    Butterworth bilinear SOS + RBJ peaking biquad
      applyFilter.m                  FIR / IIR tf / SOS, causal or zero-phase
      freqResponse.m                 analytic complex response at frequencies
      estimateGain.m                 least-squares / rms / energy gain estimate
      estimateSnr.m                  tone-projection or reference-based SNR
      estimateThd.m                  coherent harmonic THD
      estimateThdPlusN.m             THD+N
      estimateFilterResponse.m       Welch cross-spectrum filter estimate
      addAwgn.m                      white/pink Gaussian noise at a set SNR
      logSweep.m                     exponential sweep + inverse filter
    +stats/                          independent statistics (no toolbox)
      pairedTTest.m                  paired t-test (betainc/betaincinv based)
      wilcoxonTest.m                 signed-rank test (normal approximation)
      bootstrapCI.m                  percentile bootstrap, subject as unit
      cohensDz.m                     Cohen's dz effect size
      holmBonferroni.m               Holm step-down correction
      rankBiserial.m                 rank-biserial effect size
    +synthetic/                      reproducible synthetic case engine
      buildSyntheticCases.m          1000 cases, seed 20260422, 4 categories
      renderSyntheticCase.m          signal pair + known ground truth
      virtualHA.m                    3-band compressor with attack/release
      injectFault.m                  clipping/dropout/dc_offset/gain_error/
                                     harmonic_distortion/latency
  gui/
    AcousticBenchGUI.m               programmatic uifigure app (no .mlapp)
    README.md                        GUI usage
  tests/
    testDsp.m                        DSP + statistics unit tests (analytic truth)
    testMeasurements.m               Hha/REOIG/PTPE on synthetic complex data
    testValidity.m                   loader/schema/masks, device metadata
    testSynthetic.m                  case reproducibility and ground truth
    testGuiConstruction.m            GUI construction, skipped without desktop
    run_all_tests.m                  suite runner (adds paths, non-zero exit on failure)
```

## Intended commands

All commands assume the repository root as the working directory.

```
# Add the toolkit to the MATLAB path (once per session)
addpath(genpath('matlab'));

# Run the full unittest suite (headless; non-zero exit on failure)
matlab -batch "addpath('matlab'); run_all_tests"

# Write the E15 cross-language reference CSV
matlab -batch "addpath('matlab'); run_cross_language_export"

# Open the GUI (desktop session)
matlab -r "addpath(genpath('matlab')); app = AcousticBenchGUI;"
```

Note on the literal E15 command `matlab -batch "run_cross_language_export"`
from the repository root: MATLAB only finds a file in the current folder or
on the search path, so this exact form requires `matlab/` to be on the path
(for example `matlab -sd matlab -batch "run_cross_language_export"`, or a
repository-root launcher that adds `matlab/` to the path). The recommended
unattended command is the `addpath('matlab')` form shown above; the export
script itself computes the repository root from its own file location, so the
working directory does not matter once it has been found.

## Public API summary

Signatures (all options are name-value arguments):

```
data  = acousticbench.loadData(matPath, 'ApplyStructuralMask',false,
                               'ApplyNaNMask',false, 'ComputeHash',false,'Strict',true)
T     = acousticbench.structuralValidityTable(containerKey)      % 98-row table
L     = acousticbench.hha(data, 'Container','M_ha2edR', 'Condition','all',
                           'Units','spl'|'pa_per_v', 'DeviceCodes',[], 'FloorDb',-200)
G     = acousticbench.reoig(data, 'Condition','measurement'|'reference', ...)
out   = acousticbench.ptpe(data, family, 'Metric','hha'|'reoig'|'threshold',
                           'Frequencies',[])
L     = acousticbench.feedbackPath(data, 'Condition','measurement', 'Units','spl', ...)
T     = acousticbench.thresholdTable(data, 'Statistic','median'|'mean', ...)
L     = acousticbench.bandLevels(valuesDb, freqHz, bands, 'FloorDb',-200)
bands = acousticbench.octaveBands('FMin',20,'FMax',22050,'Centers',[])
bands = acousticbench.thirdOctaveBands('FMin',20,'FMax',22050,'Centers',[])
refs  = acousticbench.referenceMetrics(data)                     % 142 E15 rows

[amp,f]      = acousticbench.dsp.fftSpectrum(x, fs, 'Window','hann','Nfft',[],
                                             'Detrend',true,'OneSided',true)
[S,f,t]      = acousticbench.dsp.stftSpectrum(x, fs, 'WindowLength',256,'Overlap',0.5, ...)
[pxx,f]      = acousticbench.dsp.welchPsd(x, fs, 'SegmentLength',[],'Overlap',0.5, ...)
[b,info]     = acousticbench.dsp.designFir(nTaps, cutoffHz, fs,
                                            'Type','lowpass','Window','hamming')
[sos,g,info] = acousticbench.dsp.designIir(type, cutoffHz, fs, order,
                                           'GainDb',0,'Q',1/sqrt(2))
y            = acousticbench.dsp.applyFilter(x, coeff, 'Method','filter'|'filtfilt')
[H,f]        = acousticbench.dsp.freqResponse(coeff, fs, freqs, 'Gain',[])
[gdb,gl,info]= acousticbench.dsp.estimateGain(output, input, 'Method','ls'|'rms'|'energy')
[snr,info]   = acousticbench.dsp.estimateSnr(signal, fs, 'ToneHz',[], 'Reference',[],
                                             'Method','auto'|'tone'|'reference')
[thd,info]   = acousticbench.dsp.estimateThd(signal, fs, toneHz, 'NHarmonics',10)
[thdn,info]  = acousticbench.dsp.estimateThdPlusN(signal, fs, toneHz,
                                                  'RemoveHarmonics',false)
[H,probe]    = acousticbench.dsp.estimateFilterResponse(input, output, fs, probeFreqs, ...)
[y,noise,snr]= acousticbench.dsp.addAwgn(signal, snrDb, 'Seed',20260422,
                                          'NoiseColor','white'|'pink')
[x,t,info]   = acousticbench.dsp.logSweep(fs, durationS, fLow, fHigh,
                                          'Amplitude',1,'FadeMs',0)

r = acousticbench.stats.pairedTTest(x, y, 'Alpha',0.05,'Tail','both')
r = acousticbench.stats.wilcoxonTest(x, y, 'Alpha',0.05,'Tail','both')
[ci,boot] = acousticbench.stats.bootstrapCI(data, statisticFcn, nResamples, seed,
                                            'Alpha',0.05)
[dz,se] = acousticbench.stats.cohensDz(x, y)
[adj,rej] = acousticbench.stats.holmBonferroni(pValues, alpha)
[r,info]  = acousticbench.stats.rankBiserial(x, y)

cases = acousticbench.synthetic.buildSyntheticCases('NumCases',1000,'Seed',20260422,
                                                    'Fs',48000,'DurationS',4)
[caseData,gt] = acousticbench.synthetic.renderSyntheticCase(caseSpec)
[out,info]    = acousticbench.synthetic.virtualHA(input, fs, 'CrossoverHz',[500 2000], ...)
[out,info]    = acousticbench.synthetic.injectFault(input, fs, faultType, ...)
```

Every function has an H1 help block with purpose, inputs, outputs, an
example and `error('acousticbench:...')` identifiers; no global state is
used (all random streams are local `RandStream` objects).

## Dataset semantics encoded here

- `Data.mat` is MATLAB v5 with `v_frq` (1x2049, 0..22050 Hz, df =
  22050/2048 = 10.7666015625 Hz), `v_fAud` (1x6 uint16: 125, 250, 500, 750,
  1000, 2000 Hz), five complex 2049x14x14x3 transfer-function containers
  (`M_ha2edM`, `M_ha2edR`, `M_ha2haf`, `M_ls2edM`, `M_ls2edR`), `M_thr_ha`
  (6x14x14x3 double, dBV) and `M_REUR` (2049x14 complex).
- Dim 2 = device code 1..14 = 7 families x {reference (odd), measurement
  (even)}: Closed Earmold 1/2, Vented Earmold 3/4, Nugget Earmold 5/6,
  Silicone Earmold 7/8, Open Dome 9/10, Tulip Dome 11/12, Power Dome 13/14.
  Dim 3 = subject 1..14; dim 4 = reinsertion 1..3.
- Units: HA-driver-source containers store pressure in Pa at 11.2 mV
  receiver drive; loudspeaker-source containers store Pa at the free-field
  reference (only ratios are calibrated); thresholds are receiver voltage at
  threshold in dBV.
  `Hha [dB SPL at 11.2 mV] = 20 log10(|p| / 20e-6)`;
  `Hha [dB re 1 Pa/V] = 20 log10(|p| / 0.0112)`.
- Measured NaNs: 18 completely invalid (device, subject, reinsertion)
  sessions in each of the five 4-D transfer containers and 19 in
  `M_thr_ha`. They are excluded and never imputed.
- Structural invalidity (stored values that are not the documented
  quantity): in the REFERENCE condition the measurement probe tube hung
  loosely around the ear, so `M_ha2edM`/`M_ls2edM` reference-condition
  values are not eardrum pressures; the reference probe tube was used with
  earmolds only, so `M_ha2edR`/`M_ls2edR` dome values are not eardrum
  pressures. Both are masked out for eardrum analyses; the
  reference-condition `M_ls2edM` values remain available as the in-situ
  free-field proxy.
- REOIG (measurement condition) =
  20 log10|M_ls2edM(meas)| - 20 log10|M_REUR|; the reference condition for
  earmolds uses `M_ls2edR(ref) - M_REUR`. The arbitrary free-field scaling
  cancels in the ratio.
- PTPE: deltaHha = Hha(RPT, meas) - Hha(RPT, ref) for earmolds;
  deltaT = T_ref - T_meas at 125 Hz for all families;
  deltaREOIG = REOIG(meas) - REOIG(ref) for earmolds.
- Expected signs (from the preprint, used as plausibility checks only):
  deltaHha < 0 at low frequency, deltaREOIG > 0, deltaT < 0.

## Cross-language contract (experiment E15)

### Input file: `results/validation/matlab_inputs.mat` (written by Python)

The Python exporter currently writes the **parallel-array form** (verified
against the generated file: 25 signals = 7 gain + 7 snr + 7 thd + 4
frequency-response, 192000 samples at 48 kHz), with `ids` as an Nx1 cellstr
and the signal matrices as `nSamples x N`.  The 1xN struct array `signals`
form described below is accepted as well; each element has fields:

| field | type | meaning |
| --- | --- | --- |
| `id` | char | case label, e.g. `'gain-0001'`; used verbatim as `test_id` |
| `category` | char | `'gain'`, `'snr'`, `'thd'` or `'frequency_response'` |
| `fs` | double | sample rate [Hz] |
| `input` | double column | stimulus |
| `output` | double column | system response (same length) |
| `clean_reference` | double column | noise-free reference |
| `tone_hz` | double | fundamental [Hz]; NaN for frequency-response cases |
| `gain_db`, `snr_db`, `thd_percent` | double | scoring only, never used for estimation |
| `freq_start_hz`, `freq_end_hz` | double | NaN for non-FR cases |

Fallback accepted: parallel arrays `ids` (cellstr Nx1), `category`
(cellstr Nx1), `fs` (Nx1), `input`/`output`/`clean_reference` (nSamples x N)
and, optionally, `tone_hz` (Nx1; the documented fallback 1000 Hz is used if
absent).

### Output file: `results/validation/matlab_reference.csv`

Header exactly `test_id,quantity,value,unit`; numbers formatted `%0.17g`;
directories created if missing.

Synthetic rows use `test_id = ids{k}` (parallel-array form) or
`test_id = signals(k).id` (struct-array form) and only the metric of the case
category:

| category | quantity | unit | MATLAB estimator |
| --- | --- | --- | --- |
| gain | `gain_db` | `dB` | `estimateGain(output,input)` (least-squares scalar gain, 20 log10 abs) |
| snr | `snr_db` | `dB` | `estimateSnr(output,fs,'ToneHz',tone_hz)` (DC+cos+sin fit, residual = noise) |
| thd | `thd_percent` | `%` | `estimateThd(output,fs,tone_hz)` (coherent harmonics 2..10 / fundamental) |
| frequency_response | (omitted) | - | no analytic reference response is available in the input file, so `fr_mae_db` is omitted as the contract allows |

Dataset rows (142 rows, also produced by `acousticbench.referenceMetrics`):

| test_id | quantity | unit | definition |
| --- | --- | --- | --- |
| `hha_band:<device_code>:<band_center_hz>` | `hha_band_db` | `dB` | M_ha2edR, measurement condition, codes 2/4/6/8, octave-band level in dB SPL, median over subjects x reinsertions. 36 rows. |
| `reoig_band:<family>:<band_center_hz>` | `reoig_db` | `dB` | measurement-condition M_ls2edM vs M_REUR: octave-band level of the occluded pressure minus octave-band level of M_REUR (i.e. ratio of mean band powers, not a mean of pointwise ratios); median over subjects x reinsertions, all 7 families. 63 rows. |
| `ptpe_hha_band:<family>:<band_center_hz>` | `ptpe_hha_db` | `dB` | band level(M_ha2edR, measurement code) - band level(M_ha2edR, reference code), 4 earmold families, median over subjects x reinsertions. 36 rows. |
| `delta_t_125:<family>` | `delta_t_db` | `dB` | T_ref - T_meas at 125 Hz, median over subjects x reinsertions, all 7 families. 7 rows. |

Octave bands: centres 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000 Hz,
edges centre/sqrt(2) and centre*sqrt(2), bins with low <= f < high, power
averaging (`acousticbench.bandLevels`). Family names are the machine-readable
keys `closed_earmold`, `vented_earmold`, `nugget_earmold`, `silicone_earmold`,
`open_dome`, `tulip_dome`, `power_dome`.

Rows with no valid observation are written as `NaN`; no value is imputed.
With the current Python input (25 signals) the script writes 142 dataset rows
and 21 synthetic rows (163 total); the 4 frequency-response case ids are
omitted because the input file has no analytic reference response for
`fr_mae_db`.  Note that the Python comparison would merge those 4 rows with
NaN expected values, producing a vacuous zero-sample `fr_mae_db` comparison
that it reports as failed; omitting them is therefore the correct reading of
the contract ("else omit") and keeps the agreement sample meaningful.

## Verification status (explicit)

| Item | Status in the authoring environment |
| --- | --- |
| MATLAB installed / licence | **NO** (MATLAB is absent; no licence available) |
| GNU Octave syntax/smoke check | **NOT POSSIBLE** (the background `brew install octave` failed because `/opt/homebrew` is not writable; `which octave` is empty) |
| MATLAB unittest suite (`tests/`) | **AUTHORED, NOT RUN** |
| GUI construction (`gui/`) | **AUTHORED, NOT RUN** |
| `run_cross_language_export.m` in MATLAB | **AUTHORED, NOT RUN**; no `matlab_reference.csv` has been produced by MATLAB |
| Static self-review | **PERFORMED**: 46 `.m` files (6571 lines) checked for ASCII safety, file-name/function-name consistency (the E15 file is a reviewed script, everything else a function/classdef), no Python-isms, no banned toolbox calls, block-keyword balance (`function/if/for/while/switch/try/arguments/classdef/methods`) and delimiter balance: 0 problems |
| Formula-level cross-check | **PERFORMED in Python, not MATLAB**: the `referenceMetrics` formulas were re-implemented independently in Python and compared with the Python production expected values (`_expected_dataset_values`, E15): all 142/142 dataset rows match to <= 1.4e-14 dB. The MATLAB synthetic estimator definitions (`estimateGain` LS, `estimateSnr` tone projection, `estimateThd` rectangular coherent harmonics) were re-implemented in Python and applied to the actual `matlab_inputs.mat` signals: gain <= 3.6e-15 dB (E15 tolerance 0.01), SNR <= 0.0085 dB (tolerance 0.05), THD <= 1.5e-12 percentage points (tolerance 0.01). This validates the *definitions*, not the MATLAB code. |

No MATLAB test has been claimed as passing. To verify:

1. Run `matlab -batch "addpath('matlab'); run_all_tests"` on R2021b+ with
   `Data.mat` present; all tests must report PASS (GUI tests are skipped in
   headless mode).
2. Run `matlab -batch "addpath('matlab'); run_cross_language_export"` after
   the Python side has written `results/validation/matlab_inputs.mat`.
3. Compare `results/validation/matlab_reference.csv` with the Python
   reference for the matched `test_id` values (E15 tolerances in
   `config/default.yaml`: 0.01 dB / 0.01 degrees for levels).
4. Open the GUI with `matlab -r "addpath(genpath('matlab')); AcousticBenchGUI;"`
   and exercise each tab and the PNG/CSV export buttons.

Reference values from the Python data audit (Python output, **not** MATLAB
output) can be used as sanity checks for the dataset rows: deltaHha at
100 Hz by family {-4.05, -0.22, -9.27, -4.67} dB (closed, vented, nugget,
silicone), deltaT(125 Hz) median -2.0 dB, REOIG(1 kHz) closed -10.92 dB and
open dome +0.47 dB, Hha median 82.84 dB SPL over 0.5-4 kHz.

## Compatibility notes / known limitations

- Targeted at R2021b+. Validators used: `mustBeNumeric`, `mustBeReal`,
  `mustBeInteger`, `mustBePositive`, `mustBeNonnegative`, `mustBeTextScalar`,
  `mustBeInRange`, plus `validatestring`/`validateattributes`-style checks in
  the function bodies. The GUI builds all components programmatically.
- `applyFilter('Method','filtfilt')` is an independent forward-backward
  implementation with odd reflection padding; it is *not* bit-identical to
  the Signal Processing Toolbox `filtfilt`.
- `wilcoxonTest` uses the tie-corrected normal approximation with continuity
  correction (documented in the H1 help); it is not an exact enumeration.
- `virtualHA` is a deliberately simplified synthetic compressor model, not a
  clinically valid hearing-aid fitting model.
- The GUI is a viewer: it masks invalid data like the analysis functions and
  never imputes. PNG export uses `exportgraphics` (R2020a+).
- The synthetic `frequency_response` category produces no E15 row because
  the input file contains no analytic reference response; this is documented
  in `run_cross_language_export.m` and is allowed by the contract.
