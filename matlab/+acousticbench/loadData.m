function data = loadData(matPath, options)
%LOADDATA Load and validate the AcousticBench Data.mat measurement file.
%
%   DATA = acousticbench.loadData() loads <repo>/Data.mat.
%   DATA = acousticbench.loadData(PATH) loads an explicit MAT-file.
%   DATA = acousticbench.loadData(PATH, 'Name', VALUE, ...) controls
%   validation and masking.
%
%   The MAT-file (MATLAB v5) must contain
%       v_frq     1x2049 double   frequency axis [Hz], 0..22050
%       v_fAud    1x6    uint16   audiometric frequencies [Hz]
%       M_ha2edM  2049x14x14x3 complex  HA driver -> eardrum, measurement probe
%       M_ha2edR  2049x14x14x3 complex  HA driver -> eardrum, reference probe
%       M_ha2haf  2049x14x14x3 complex  HA driver -> HA microphone (feedback)
%       M_ls2edM  2049x14x14x3 complex  loudspeaker -> eardrum, measurement probe
%       M_ls2edR  2049x14x14x3 complex  loudspeaker -> eardrum, reference probe
%       M_thr_ha  6x14x14x3    double   hearing threshold [dBV]
%       M_REUR    2049x14      complex  real-ear unaided response
%
%   Validity is reported, never imputed:
%       DATA.valid.(KEY)       measured-finiteness AND structural validity
%       DATA.structural.(KEY)  1x14 logical structural validity per device
%       DATA.nanSession.(KEY)  fully-NaN (device, subject, reinsertion) sessions
%       DATA.masked.(KEY)      values with invalid entries set to NaN, only
%                              when 'ApplyNaNMask' / 'ApplyStructuralMask'
%                              are requested.
%
%   Structural validity rules (from Documentation.pdf / preprint):
%       M_ha2edM, M_ls2edM  meaningful only in the MEASUREMENT condition
%                           (in the reference condition the measurement probe
%                           tube hung loosely around the ear).
%       M_ha2edR, M_ls2edR  meaningful only for EARMOLDS (codes 1..8); the
%                           reference probe was used only with earmolds.
%       M_ha2haf, M_thr_ha, M_REUR  no structural restriction.
%
%   Name-Value arguments
%       'ApplyStructuralMask' (false)  set structurally invalid entries to NaN
%       'ApplyNaNMask'        (false)  set measured-NaN entries to NaN
%       'ComputeHash'         (false)  compute the SHA-256 fingerprint (needs JVM)
%       'Strict'              (true)   enforce the uniform 10.7666 Hz DFT grid
%
%   Output DATA (struct)
%       path, fileName, fileSizeBytes, matFormat, sha256, loadedAt
%       frequency            2049x1 double [Hz]
%       audiometricFrequency 6x1 double [Hz]
%       subjects             14x1 double
%       reinsertions         3x1 double
%       devices              1x14 struct (see acousticbench.deviceTable)
%       variables            struct with the raw containers
%       valid, structural, nanSession, masked, meta, warnings
%
%   Example
%       data = acousticbench.loadData('Data.mat');
%       nInvalid = sum(data.nanSession.M_ha2edR(:));
%
%   Error identifiers: acousticbench:loadData:fileNotFound,
%   acousticbench:loadData:missingVariable, acousticbench:loadData:schema,
%   acousticbench:loadData:frequencyAxis.
%
%   See also acousticbench.structuralValidityTable, acousticbench.hha.

arguments
    matPath {mustBeTextScalar} = ''
    options.ApplyStructuralMask (1,1) logical = false
    options.ApplyNaNMask (1,1) logical = false
    options.ComputeHash (1,1) logical = false
    options.Strict (1,1) logical = true
end

c = acousticbench.constants();
devices = acousticbench.deviceTable();

%% Locate the file -------------------------------------------------------
if strlength(string(matPath)) == 0
    here = fileparts(mfilename('fullpath'));      % .../matlab/+acousticbench
    matlabDir = fileparts(here);                  % .../matlab
    repoRoot = fileparts(matlabDir);              % repository root
    matPath = fullfile(repoRoot, 'Data.mat');
end
matPath = char(matPath);

if exist(matPath, 'file') ~= 2
    error('acousticbench:loadData:fileNotFound', ...
        ['Data file not found: %s. Place Data.mat at the repository root ' ...
         '(see DATA_LICENSE.md) or pass an explicit path.'], matPath);
end

fileInfo = dir(matPath);
fileInfo = fileInfo(1);

matFormat = detectMatFormat(matPath);
S = load(matPath);

%% Validate schema -------------------------------------------------------
[variables, schemaWarnings] = validateVariables(S, c, options.Strict);

data = struct();
data.path = matPath;
[~, name, ext] = fileparts(matPath);
data.fileName = [name ext];
data.fileSizeBytes = double(fileInfo.bytes);
data.matFormat = matFormat;
data.loadedAt = datestr(now, 30);

if options.ComputeHash
    data.sha256 = sha256OfFile(matPath);
else
    data.sha256 = '';
end

data.frequency = double(variables.v_frq(:));
data.audiometricFrequency = double(variables.v_fAud(:));
data.subjects = (1:c.nSubjects)';
data.reinsertions = (1:c.nReinsertions)';
data.devices = devices;
data.variables = variables;

%% Validity masks --------------------------------------------------------
transferContainers = {'M_ha2edM', 'M_ha2edR', 'M_ha2haf', 'M_ls2edM', 'M_ls2edR'};
allContainers = [transferContainers, {'M_thr_ha', 'M_REUR'}];

data.structural = struct();
for k = 1:numel(allContainers)
    key = allContainers{k};
    data.structural.(key) = structuralMaskFor(key, devices);
end

data.valid = struct();
data.nanSession = struct();
for k = 1:numel(transferContainers)
    key = transferContainers{k};
    values = variables.(key);
    structural = reshape(data.structural.(key), 1, c.nDevices, 1, 1);
    data.valid.(key) = isfinite(values) & structural;
    data.nanSession.(key) = squeeze(all(~isfinite(values), 1));
end
data.valid.M_thr_ha = isfinite(variables.M_thr_ha);
data.nanSession.M_thr_ha = squeeze(all(~isfinite(variables.M_thr_ha), 1));
data.valid.M_REUR = isfinite(variables.M_REUR);
data.nanSession.M_REUR = all(~isfinite(variables.M_REUR), 1)';

%% Optional masking ------------------------------------------------------
data.masked = struct();
if options.ApplyStructuralMask || options.ApplyNaNMask
    for k = 1:numel(transferContainers)
        key = transferContainers{k};
        data.masked.(key) = maskContainer( ...
            variables.(key), data.valid.(key), ...
            options.ApplyStructuralMask, options.ApplyNaNMask);
    end
    for k = 1:2
        key = allContainers{numel(transferContainers) + k};
        data.masked.(key) = maskContainer( ...
            variables.(key), data.valid.(key), ...
            options.ApplyStructuralMask, options.ApplyNaNMask);
    end
end

%% Metadata --------------------------------------------------------------
data.meta = struct( ...
    'nFrequencies', c.nFrequencies, ...
    'nThresholdFrequencies', c.nThresholdFrequencies, ...
    'nDevices', c.nDevices, ...
    'nSubjects', c.nSubjects, ...
    'nReinsertions', c.nReinsertions, ...
    'nFamilies', c.nFamilies, ...
    'nyquistHz', c.nyquistHz, ...
    'frequencyResolutionHz', c.frequencyResolutionHz, ...
    'pRefPa', c.pRefPa, ...
    'uHaDriveV', c.uHaDriveV, ...
    'transferContainers', {transferContainers}, ...
    'thresholdContainer', 'M_thr_ha', ...
    'reurContainer', 'M_REUR', ...
    'invalidPolicy', 'exclude');

warnings = schemaWarnings;
if options.ComputeHash == false
    warnings{end + 1} = 'SHA-256 fingerprint not computed (ComputeHash=false).';
end
data.warnings = warnings;
end

% =======================================================================
function matFormat = detectMatFormat(path)
fid = fopen(path, 'r');
if fid < 0
    error('acousticbench:loadData:fileNotFound', 'Cannot open %s for reading.', path);
end
header = fread(fid, 128, '*uint8')';
fclose(fid);
headerText = char(header);
if strncmp(headerText, 'MATLAB 7.3', 10)
    matFormat = 'v7.3 (HDF5)';
else
    matFormat = 'v5';
end
end

% =======================================================================
function [variables, warnings] = validateVariables(S, c, strict)
names = { ...
    'v_frq', 'v_fAud', 'M_ha2edM', 'M_ha2edR', 'M_ha2haf', ...
    'M_ls2edM', 'M_ls2edR', 'M_thr_ha', 'M_REUR'};
shapes = { ...
    [1, c.nFrequencies], ...
    [1, c.nThresholdFrequencies], ...
    [c.nFrequencies, c.nDevices, c.nSubjects, c.nReinsertions], ...
    [c.nFrequencies, c.nDevices, c.nSubjects, c.nReinsertions], ...
    [c.nFrequencies, c.nDevices, c.nSubjects, c.nReinsertions], ...
    [c.nFrequencies, c.nDevices, c.nSubjects, c.nReinsertions], ...
    [c.nFrequencies, c.nDevices, c.nSubjects, c.nReinsertions], ...
    [c.nThresholdFrequencies, c.nDevices, c.nSubjects, c.nReinsertions], ...
    [c.nFrequencies, c.nSubjects]};
mustBeComplex = [false, false, true, true, true, true, true, false, true];

variables = struct();
warnings = {};

for k = 1:numel(names)
    key = names{k};
    if ~isfield(S, key)
        error('acousticbench:loadData:missingVariable', ...
            'Data.mat is missing the required variable %s.', key);
    end
    value = S.(key);
    if any(strcmp(key, {'v_frq', 'v_fAud'}))
        if numel(value) ~= prod(shapes{k})
            error('acousticbench:loadData:schema', ...
                '%s must have %d elements, got %d.', key, prod(shapes{k}), numel(value));
        end
        value = reshape(value, shapes{k});
    elseif ~isequal(size(value), shapes{k})
        error('acousticbench:loadData:schema', ...
            '%s must have size [%s], got [%s].', key, ...
            num2str(shapes{k}), num2str(size(value)));
    end
    if mustBeComplex(k)
        if isreal(value)
            error('acousticbench:loadData:schema', ...
                '%s must be complex-valued (stored as complex double).', key);
        end
    elseif ~isreal(value)
        error('acousticbench:loadData:schema', ...
            '%s must be real-valued.', key);
    end
    if ~any(isfinite(value(:)))
        error('acousticbench:loadData:schema', '%s contains no finite values.', key);
    end
    if any(isinf(value(:)))
        error('acousticbench:loadData:schema', '%s contains infinite values.', key);
    end
    variables.(key) = value;
end

frequency = double(variables.v_frq(:));
audiometric = double(variables.v_fAud(:));

if frequency(1) ~= 0
    warnings{end + 1} = sprintf('v_frq does not start at 0 Hz (starts at %g Hz).', frequency(1));
end
diffs = diff(frequency);
if any(diffs <= 0)
    error('acousticbench:loadData:frequencyAxis', 'v_frq must be strictly increasing.');
end
if strict
    if any(abs(diffs - c.frequencyResolutionHz) > 1e-6 * c.frequencyResolutionHz)
        error('acousticbench:loadData:frequencyAxis', ...
            ['v_frq is not a uniform DFT grid with df = %.10f Hz ' ...
             '(observed median df = %.10f Hz).'], ...
            c.frequencyResolutionHz, median(diffs));
    end
    if abs(frequency(end) - c.nyquistHz) > 1e-6 * c.nyquistHz
        error('acousticbench:loadData:frequencyAxis', ...
            'v_frq must end at the Nyquist frequency %g Hz, got %g Hz.', ...
            c.nyquistHz, frequency(end));
    end
elseif any(abs(diffs - median(diffs)) > 1e-6 * c.frequencyResolutionHz)
    warnings{end + 1} = 'v_frq is not exactly uniform (Strict=false).';
end
if any(diff(audiometric) <= 0)
    error('acousticbench:loadData:schema', 'v_fAud must be strictly increasing.');
end
if numel(audiometric) ~= c.nThresholdFrequencies
    error('acousticbench:loadData:schema', ...
        'v_fAud must have %d entries, got %d.', c.nThresholdFrequencies, numel(audiometric));
end
end

% =======================================================================
function mask = structuralMaskFor(key, devices)
switch key
    case {'M_ha2edM', 'M_ls2edM'}
        mask = reshape([devices.isMeasurement], 1, []);
    case {'M_ha2edR', 'M_ls2edR'}
        mask = reshape([devices.isEarmold], 1, []);
    otherwise
        mask = true(1, numel(devices));
end
end

% =======================================================================
function masked = maskContainer(values, valid, applyStructural, applyNaN)
if isempty(valid)
    masked = values;
    return;
end
keep = true(size(values));
if applyNaN
    keep = keep & isfinite(values);
end
if applyStructural
    keep = keep & valid;
end
masked = values;
if isreal(values)
    masked(~keep) = NaN;
else
    masked(~keep) = complex(NaN, NaN);
end
end

% =======================================================================
function digestHex = sha256OfFile(path)
if ~usejava('jvm')
    error('acousticbench:loadData:hashUnavailable', ...
        'ComputeHash=true requires a Java VM (usejava(''jvm'') is false).');
end
md = java.security.MessageDigest.getInstance('SHA-256');
fid = fopen(path, 'r');
if fid < 0
    error('acousticbench:loadData:fileNotFound', 'Cannot open %s for hashing.', path);
end
cleanup = onCleanup(@() fclose(fid));
while ~feof(fid)
    block = fread(fid, 1 << 20, '*uint8');
    if ~isempty(block)
        md.update(block);
    end
end
raw = typecast(md.digest(), 'uint8');
digestHex = sprintf('%02x', raw);
end
