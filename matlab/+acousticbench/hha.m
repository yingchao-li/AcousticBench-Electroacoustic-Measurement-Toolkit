function [levelsDb, freqHz, info] = hha(data, options)
%HHA Hearing-aid driver response at the eardrum in dB.
%
%   [LEVELSDB, FREQHZ] = acousticbench.hha(DATA) returns the hearing-aid
%   driver response at the eardrum in dB SPL at the 11.2 mV receiver drive
%   for the default container M_ha2edR (reference probe tube).
%
%   [LEVELSDB, FREQHZ] = acousticbench.hha(DATA, 'Name', VALUE, ...)
%   controls container, condition, units and selection.  Structurally
%   invalid entries and measured NaNs are always returned as NaN; no
%   imputation is performed.
%
%   Inputs
%       DATA   dataset struct from acousticbench.loadData
%
%   Name-Value arguments
%       'Container'    'M_ha2edR' (default) or 'M_ha2edM'
%       'Condition'    'all' (default) | 'reference' | 'measurement'
%       'Units'        'spl' (default, dB re 20 uPa) or 'pa_per_v'
%                      (dB re 1 Pa/V at the 11.2 mV drive)
%       'DeviceCodes'  subset of 1..14 (default all)
%       'Subjects'     subset of 1..14 (default all)
%       'Reinsertions' subset of 1..3 (default all)
%       'FloorDb'      magnitude floor in dB (default -200)
%
%   Outputs
%       LEVELSDB   nFreq x nDevice x nSubject x nReinsertion double, NaN
%                  where invalid
%       FREQHZ     nFreq x 1 frequency axis [Hz]
%       INFO       struct with container, units, device codes, subjects,
%                  reinsertions and the number of finite values
%
%   Units
%       Hha(dB SPL at 11.2 mV) = 20 log10(|p| / 20e-6)
%       Hha(dB re Pa/V)        = 20 log10(|p| / 0.0112)
%
%   Example
%       data = acousticbench.loadData('Data.mat');
%       L = acousticbench.hha(data, 'Condition', 'measurement');
%       medianLevel = median(L(1:2049), 'omitnan');
%
%   Error identifiers: acousticbench:hha:unknownContainer,
%   acousticbench:hha:emptySelection.
%
%   See also acousticbench.reoig, acousticbench.ptpe,
%   acousticbench.bandLevels.

arguments
    data struct
    options.Container {mustBeTextScalar} = 'M_ha2edR'
    options.Condition {mustBeTextScalar} = 'all'
    options.Units {mustBeTextScalar} = 'spl'
    options.DeviceCodes double = []
    options.Subjects double = []
    options.Reinsertions double = []
    options.FloorDb (1,1) double = -200
end

c = acousticbench.constants();
container = validatestring(char(options.Container), {'M_ha2edR', 'M_ha2edM'}, ...
    mfilename, 'Container');
condition = validatestring(char(options.Condition), ...
    {'all', 'reference', 'measurement'}, mfilename, 'Condition');
units = validatestring(char(options.Units), {'spl', 'pa_per_v'}, mfilename, 'Units');

values = data.variables.(container);
valid = data.valid.(container);

[deviceIndex, subjectIndex, reinsertionIndex] = selectAxes( ...
    data, options.DeviceCodes, options.Subjects, options.Reinsertions, ...
    condition);

values = values(:, deviceIndex, subjectIndex, reinsertionIndex);
valid = valid(:, deviceIndex, subjectIndex, reinsertionIndex);

levelsDb = amplitudeToDb(values, options.FloorDb);
switch units
    case 'spl'
        levelsDb = levelsDb - 20 * log10(c.pRefPa);
    case 'pa_per_v'
        levelsDb = levelsDb - 20 * log10(c.uHaDriveV);
end
levelsDb(~valid) = NaN;

freqHz = data.frequency;

if nargout > 2
    info = struct( ...
        'container', container, ...
        'condition', condition, ...
        'units', units, ...
        'deviceCodes', [data.devices(deviceIndex).code], ...
        'subjects', data.subjects(subjectIndex)', ...
        'reinsertions', data.reinsertions(reinsertionIndex)', ...
        'nValid', nnz(isfinite(levelsDb)));
end
end

% =======================================================================
function db = amplitudeToDb(values, floorDb)
floorAmplitude = 10 ^ (floorDb / 20);
db = 20 * log10(max(abs(values), floorAmplitude));
end

% =======================================================================
function [deviceIndex, subjectIndex, reinsertionIndex] = selectAxes( ...
    data, deviceCodes, subjects, reinsertions, condition)
deviceIndex = 1:numel(data.devices);
if ~strcmp(condition, 'all')
    keep = arrayfun(@(d) strcmp(d.condition, condition), data.devices);
    deviceIndex = deviceIndex(keep);
end
deviceIndex = restrictIndex(deviceIndex, deviceCodes, 'DeviceCodes');
subjectIndex = restrictIndex(1:numel(data.subjects), subjects, 'Subjects');
reinsertionIndex = restrictIndex(1:numel(data.reinsertions), reinsertions, 'Reinsertions');
end

% =======================================================================
function index = restrictIndex(index, wanted, argumentName)
if isempty(wanted)
    return;
end
wanted = unique(wanted(:)');
index = index(ismember(index, wanted));
if isempty(index)
    error('acousticbench:hha:emptySelection', ...
        'Selection %s = [%s] is empty.', argumentName, num2str(wanted));
end
end
