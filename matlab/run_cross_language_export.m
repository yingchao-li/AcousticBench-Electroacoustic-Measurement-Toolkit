%RUN_CROSS_LANGUAGE_EXPORT Cross-language reference export (experiment E15).
%
%   This script reads the published Data.mat and, when present,
%   results/validation/matlab_inputs.mat, computes the MATLAB reference
%   values and writes the long-format table
%       results/validation/matlab_reference.csv
%   with the EXACT header
%       test_id,quantity,value,unit
%   Numbers are written with the format %0.17g.  Directories are created
%   when missing.  The script never prompts, never opens a GUI and prints
%   one final one-line summary.
%
%   INVOCATION (from the repository root)
%       run('matlab/run_cross_language_export.m')        % used by Python E15
%       matlab -batch "addpath('matlab'); run_cross_language_export"
%   The script resolves the repository root from its own file location (with
%   which()/pwd fallbacks), so the working directory does not matter once the
%   file has been found.  The optional environment variables
%   ACOUSTICBENCH_DATA, ACOUSTICBENCH_INPUT and ACOUSTICBENCH_OUTPUT override
%   the default paths.
%
%   INPUT FILE SCHEMA (results/validation/matlab_inputs.mat, written by the
%   Python implementation of E15; MATLAB v5).  The Python exporter writes
%   PARALLEL ARRAYS:
%       ids             cellstr Nx1, e.g. 'gain-0001' (used as test_id)
%       category        cellstr Nx1: 'gain' | 'snr' | 'thd' | 'frequency_response'
%       fs              1xN (or Nx1) double sample rate [Hz]
%       input           nSamples x N double
%       output          nSamples x N double
%       clean_reference nSamples x N double (may be absent)
%       tone_hz         1xN double fundamental [Hz]; NaN for FR cases
%       gain_db, snr_db, thd_percent  scoring only, never used for estimation
%       freq_start_hz, freq_end_hz    NaN for non-FR cases
%   A 1xN struct array named `signals` with fields id, category, fs, input,
%   output, clean_reference, tone_hz ... is also accepted (snake_case or
%   camelCase field names).
%
%   OUTPUT ROWS (the complete E15 contract)
%   Synthetic signals: test_id = ids{k}, one row appropriate to the category:
%       'gain'  quantity 'gain_db',      unit 'dB'  -> estimateGain(output,input)
%       'snr'   quantity 'snr_db',       unit 'dB'  -> estimateSnr(output,fs,'ToneHz',tone_hz)
%       'thd'   quantity 'thd_percent',  unit '%'   -> estimateThd(output,fs,tone_hz)
%       'frequency_response'  no row: the input file contains no analytic
%               reference response for 'fr_mae_db', and the contract allows
%               omitting it ("else omit").  (Emitting a NaN row would create
%               a vacuous zero-sample comparison on the Python side.)
%
%   Dataset references (see acousticbench.referenceMetrics for the exact
%   definitions; octave bands 63, 125, 250, 500, 1000, 2000, 4000, 8000,
%   16000 Hz, edges centre/sqrt(2), power averaging):
%       'hha_band:<device_code>:<band_center_hz>'   'hha_band_db',   'dB'
%           36 rows: M_ha2edR measurement codes 2/4/6/8, dB SPL, median
%           over subjects x reinsertions.
%       'reoig_band:<family>:<band_center_hz>'      'reoig_db',      'dB'
%           63 rows: band level(M_ls2edM measurement code) minus band
%           level(M_REUR), i.e. ratio of mean band powers, all 7 families.
%       'ptpe_hha_band:<family>:<band_center_hz>'   'ptpe_hha_db',   'dB'
%           36 rows: band level(measurement code) - band level(reference
%           code) of M_ha2edR, 4 earmold families.
%       'delta_t_125:<family>'                      'delta_t_db',    'dB'
%           7 rows: T_ref - T_meas at 125 Hz.
%
%   See also acousticbench.referenceMetrics, acousticbench.loadData,
%   acousticbench.dsp.estimateGain, acousticbench.dsp.estimateSnr,
%   acousticbench.dsp.estimateThd.

scriptFile = resolveScriptFile(mfilename('fullpath'));
matlabDir = fileparts(scriptFile);
repoRoot = fileparts(matlabDir);
addpath(genpath(matlabDir));
rehash;

dataPath = environmentOrDefault('ACOUSTICBENCH_DATA', ...
    fullfile(repoRoot, 'Data.mat'));
inputPath = environmentOrDefault('ACOUSTICBENCH_INPUT', ...
    fullfile(repoRoot, 'results', 'validation', 'matlab_inputs.mat'));
outputPath = environmentOrDefault('ACOUSTICBENCH_OUTPUT', ...
    fullfile(repoRoot, 'results', 'validation', 'matlab_reference.csv'));

runCrossLanguageExport(dataPath, inputPath, outputPath);

% =======================================================================
% Local functions
% =======================================================================
function scriptFile = resolveScriptFile(candidate)
if ~isempty(candidate) && exist(candidate, 'file') == 2
    scriptFile = candidate;
    return;
end
fromPath = which('run_cross_language_export');
if ~isempty(fromPath) && exist(fromPath, 'file') == 2
    scriptFile = fromPath;
    return;
end
fromPwd = fullfile(pwd, 'matlab', 'run_cross_language_export.m');
if exist(fromPwd, 'file') == 2
    scriptFile = fromPwd;
    return;
end
error('acousticbench:export:noPath', ...
    'Cannot determine the location of run_cross_language_export.m.');
end

% =======================================================================
function value = environmentOrDefault(variableName, defaultPath)
value = getenv(variableName);
if isempty(value)
    value = defaultPath;
end
end

% =======================================================================
function runCrossLanguageExport(dataPath, inputPath, outputPath)
if exist(dataPath, 'file') ~= 2
    error('acousticbench:export:noData', ...
        ['Data.mat not found at %s; place the published Data.mat at the ' ...
         'repository root.'], dataPath);
end

outputDir = fileparts(outputPath);
if ~isempty(outputDir) && ~isfolder(outputDir)
    mkdir(outputDir);
end

%% Dataset reference rows ------------------------------------------------
data = acousticbench.loadData(dataPath);
datasetRows = acousticbench.referenceMetrics(data);
nDatasetRows = numel(datasetRows);
fprintf('[cross-language] Data.mat loaded (%s, %.1f MB); dataset rows: %d\n', ...
    data.matFormat, data.fileSizeBytes / 1024 ^ 2, nDatasetRows);

%% Synthetic signal rows -------------------------------------------------
rows = datasetRows;
nSignals = 0;
nSyntheticRows = 0;
nFrequencyResponseOmitted = 0;
if exist(inputPath, 'file') == 2
    contents = load(inputPath);
    try
        cases = parseInputCases(contents);
    catch err
        error('acousticbench:export:badInput', ...
            'Invalid matlab_inputs.mat: %s', err.message);
    end
    nSignals = numel(cases);
    for k = 1:nSignals
        caseSpec = cases(k);
        switch lower(char(caseSpec.category))
            case 'frequency_response'
                nFrequencyResponseOmitted = nFrequencyResponseOmitted + 1;
            otherwise
                signalRows = syntheticRowsForCase(caseSpec);
                rows = [rows, signalRows]; %#ok<AGROW>
                nSyntheticRows = nSyntheticRows + numel(signalRows);
        end
    end
    fprintf(['[cross-language] signals: %d (%d synthetic metric rows, ' ...
             '%d frequency-response cases omitted by contract)\n'], ...
        nSignals, nSyntheticRows, nFrequencyResponseOmitted);
else
    warning('acousticbench:export:missingInput', ...
        ['matlab_inputs.mat not found (%s); writing the %d dataset rows ' ...
         'only. Run the Python E15 input generator first.'], ...
        inputPath, nDatasetRows);
end

%% Write the CSV ---------------------------------------------------------
fid = fopen(outputPath, 'w');
if fid < 0
    error('acousticbench:export:cannotWrite', ...
        'Cannot open %s for writing.', outputPath);
end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, 'test_id,quantity,value,unit\n');
for k = 1:numel(rows)
    fprintf(fid, '%s,%s,%0.17g,%s\n', ...
        rows(k).testId, rows(k).quantity, rows(k).value, rows(k).unit);
end

fprintf('[cross-language] wrote %d rows (%d dataset, %d synthetic) to %s\n', ...
    numel(rows), nDatasetRows, nSyntheticRows, outputPath);
end

% =======================================================================
function cases = parseInputCases(contents)
% Normalised struct array with fields id, category, fs, input, output,
% cleanReference, toneHz.  Supports the struct-array form and the parallel
% arrays written by the Python E15 exporter.
if isfield(contents, 'signals') && isstruct(contents.signals) && ~isempty(contents.signals)
    rawSignals = contents.signals;
    n = numel(rawSignals);
    cases = repmat(normalisedCase(), 1, n);
    for k = 1:n
        raw = rawSignals(k);
        cases(k).id = charId(getFieldOr(raw, {'id'}, ''));
        cases(k).category = char(getFieldOr(raw, {'category'}, ''));
        cases(k).fs = double(getFieldOr(raw, {'fs'}, NaN));
        cases(k).input = double(getFieldOr(raw, {'input'}, []));
        cases(k).output = double(getFieldOr(raw, {'output'}, []));
        cases(k).cleanReference = double(getFieldOr(raw, ...
            {'clean_reference', 'cleanReference'}, []));
        cases(k).toneHz = double(getFieldOr(raw, {'tone_hz', 'toneHz'}, NaN));
        cases(k) = validateCase(cases(k));
    end
    return;
end

if isfield(contents, 'ids') && isfield(contents, 'category') && ...
        isfield(contents, 'fs') && isfield(contents, 'input') && ...
        isfield(contents, 'output')
    ids = contents.ids;
    categories = contents.category;
    fsValues = double(contents.fs);
    inputs = double(contents.input);
    outputs = double(contents.output);
    n = numel(ids);
    if isempty(fsValues)
        error('acousticbench:export:badInput', 'ids/fs must not be empty.');
    end
    if numel(fsValues) == 1
        fsValues = repmat(fsValues(1), n, 1);
    end
    if isfield(contents, 'tone_hz') && numel(contents.tone_hz) == n
        toneValues = double(contents.tone_hz);
    else
        toneValues = NaN(n, 1);
    end
    cleanValues = [];
    if isfield(contents, 'clean_reference') && ~isempty(contents.clean_reference)
        cleanValues = double(contents.clean_reference);
    end
    cases = repmat(normalisedCase(), 1, n);
    for k = 1:n
        cases(k).id = charId(ids(k));
        cases(k).category = char(categories(k));
        cases(k).fs = fsValues(k);
        cases(k).input = inputs(:, k);
        cases(k).output = outputs(:, k);
        if ~isempty(cleanValues)
            cases(k).cleanReference = cleanValues(:, k);
        end
        cases(k).toneHz = toneValues(k);
        cases(k) = validateCase(cases(k));
    end
    return;
end

error('acousticbench:export:badInput', ...
    ['matlab_inputs.mat must contain either a struct array `signals` or ' ...
     'the parallel arrays ids, category, fs, input, output.']);
end

% =======================================================================
function template = normalisedCase()
template = struct( ...
    'id', '', ...
    'category', '', ...
    'fs', NaN, ...
    'input', [], ...
    'output', [], ...
    'cleanReference', [], ...
    'toneHz', NaN);
end

% =======================================================================
function value = getFieldOr(structValue, names, defaultValue)
value = defaultValue;
for k = 1:numel(names)
    if isfield(structValue, names{k})
        value = structValue.(names{k});
        return;
    end
end
end

% =======================================================================
function idString = charId(id)
if ischar(id)
    idString = id;
elseif isstring(id) && isscalar(id)
    idString = char(id);
elseif iscell(id) && numel(id) == 1
    idString = char(id{1});
elseif isnumeric(id) && isscalar(id) && isfinite(id)
    idString = sprintf('signal-%04d', round(id));
else
    error('acousticbench:export:badInput', ...
        'Each case id must be a char label (or a numeric scalar).');
end
end

% =======================================================================
function caseSpec = validateCase(caseSpec)
if isempty(caseSpec.id) || isempty(caseSpec.category)
    error('acousticbench:export:badInput', ...
        'Case id and category must be non-empty.');
end
if ~isscalar(caseSpec.fs) || ~isfinite(caseSpec.fs) || caseSpec.fs <= 0
    error('acousticbench:export:badInput', ...
        'Case %s has an invalid fs.', caseSpec.id);
end
if isempty(caseSpec.input) || isempty(caseSpec.output) || ...
        numel(caseSpec.input) ~= numel(caseSpec.output)
    error('acousticbench:export:badInput', ...
        'Case %s: input/output must be non-empty and of equal length.', ...
        caseSpec.id);
end
caseSpec.input = double(caseSpec.input(:));
caseSpec.output = double(caseSpec.output(:));
caseSpec.category = lower(strtrim(char(caseSpec.category)));
allowed = {'gain', 'snr', 'thd', 'frequency_response'};
if ~any(strcmp(caseSpec.category, allowed))
    error('acousticbench:export:badInput', ...
        'Case %s has unknown category "%s".', caseSpec.id, caseSpec.category);
end
if strcmp(caseSpec.category, 'snr') || strcmp(caseSpec.category, 'thd')
    if ~isfinite(caseSpec.toneHz)
        % Documented fallback for a parallel-array file without tone_hz.
        caseSpec.toneHz = 1000;
    end
end
end

% =======================================================================
function rows = syntheticRowsForCase(caseSpec)
rows = repmat(struct('testId', '', 'quantity', '', 'value', NaN, 'unit', ''), 1, 0);
switch caseSpec.category
    case 'gain'
        gainDb = acousticbench.dsp.estimateGain(caseSpec.output, caseSpec.input);
        rows(end + 1) = makeRow(caseSpec.id, 'gain_db', gainDb, 'dB');
    case 'snr'
        if caseSpec.toneHz <= 0 || caseSpec.toneHz >= caseSpec.fs / 2
            error('acousticbench:export:badInput', ...
                'SNR case %s needs 0 < tone_hz < fs/2.', caseSpec.id);
        end
        snrDb = acousticbench.dsp.estimateSnr(caseSpec.output, ...
            caseSpec.fs, 'ToneHz', caseSpec.toneHz);
        rows(end + 1) = makeRow(caseSpec.id, 'snr_db', snrDb, 'dB');
    case 'thd'
        if caseSpec.toneHz <= 0 || caseSpec.toneHz >= caseSpec.fs / 2
            error('acousticbench:export:badInput', ...
                'THD case %s needs 0 < tone_hz < fs/2.', caseSpec.id);
        end
        thdPercent = acousticbench.dsp.estimateThd(caseSpec.output, ...
            caseSpec.fs, caseSpec.toneHz);
        rows(end + 1) = makeRow(caseSpec.id, 'thd_percent', thdPercent, '%');
    otherwise
        % frequency_response: intentionally omitted (see header comment).
end
end

% =======================================================================
function row = makeRow(testId, quantity, value, unit)
row = struct('testId', testId, 'quantity', quantity, 'value', value, 'unit', unit);
end
