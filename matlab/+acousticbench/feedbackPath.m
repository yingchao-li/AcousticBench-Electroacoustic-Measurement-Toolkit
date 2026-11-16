function [levelsDb, freqHz, info] = feedbackPath(data, options)
%FEEDBACKPATH Acoustic feedback path from the HA driver to the HA microphone.
%
%   [LEVELSDB, FREQHZ] = acousticbench.feedbackPath(DATA) returns the
%   hearing-aid driver -> hearing-aid microphone transfer function in
%   dB SPL at the 11.2 mV receiver drive (container M_ha2haf).  This is the
%   acoustic feedback path of the earpiece as measured with the earpiece
%   inserted; it is available for all 14 device codes (the hearing-aid
%   microphone is part of the device).
%
%   [LEVELSDB, FREQHZ] = acousticbench.feedbackPath(DATA, 'Name', VALUE, ...)
%
%   Name-Value arguments
%       'Condition'    'measurement' (default) | 'reference' | 'all'
%       'Units'        'spl' (default) | 'pa_per_v'
%       'DeviceCodes'  subset of 1..14 (default all)
%       'Subjects'     subset of 1..14 (default all)
%       'Reinsertions' subset of 1..3 (default all)
%       'FloorDb'      magnitude floor in dB (default -200)
%
%   Outputs
%       LEVELSDB  nFreq x nDevice x nSubject x nReinsertion double (NaN invalid)
%       FREQHZ    frequency axis [Hz]
%       INFO      struct with condition, units, selection and counts
%
%   The feedback path is not affected by the probe-tube presence beyond its
%   (small) effect through the occluded ear canal; it is used to describe
%   the acoustic coupling of an earpiece, not to derive a stable-gain
%   estimate (which would also require the forward gain of a hearing aid).
%
%   Example
%       data = acousticbench.loadData('Data.mat');
%       [L, f] = acousticbench.feedbackPath(data, 'DeviceCodes', 2);
%       levelAt1kHz = L(abs(f - 1000) == min(abs(f - 1000)));
%
%   See also acousticbench.hha.

arguments
    data struct
    options.Condition {mustBeTextScalar} = 'measurement'
    options.Units {mustBeTextScalar} = 'spl'
    options.DeviceCodes double = []
    options.Subjects double = []
    options.Reinsertions double = []
    options.FloorDb (1,1) double = -200
end

c = acousticbench.constants();
condition = validatestring(char(options.Condition), ...
    {'measurement', 'reference', 'all'}, mfilename, 'Condition');
units = validatestring(char(options.Units), {'spl', 'pa_per_v'}, mfilename, 'Units');

deviceIndex = 1:numel(data.devices);
if ~strcmp(condition, 'all')
    keep = arrayfun(@(d) strcmp(d.condition, condition), data.devices);
    deviceIndex = deviceIndex(keep);
end
deviceIndex = restrictIndex(deviceIndex, options.DeviceCodes, 'DeviceCodes');
subjectIndex = restrictIndex(1:numel(data.subjects), options.Subjects, 'Subjects');
reinsertionIndex = restrictIndex(1:numel(data.reinsertions), options.Reinsertions, 'Reinsertions');

values = data.variables.M_ha2haf(:, deviceIndex, subjectIndex, reinsertionIndex);
valid = data.valid.M_ha2haf(:, deviceIndex, subjectIndex, reinsertionIndex);

floorAmplitude = 10 ^ (options.FloorDb / 20);
levelsDb = 20 * log10(max(abs(values), floorAmplitude));
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
        'container', 'M_ha2haf', ...
        'condition', condition, ...
        'units', units, ...
        'deviceCodes', [data.devices(deviceIndex).code], ...
        'subjects', data.subjects(subjectIndex)', ...
        'reinsertions', data.reinsertions(reinsertionIndex)', ...
        'nValid', nnz(isfinite(levelsDb)));
end
end

% =======================================================================
function index = restrictIndex(index, wanted, argumentName)
if isempty(wanted)
    return;
end
wanted = unique(wanted(:)');
index = index(ismember(index, wanted));
if isempty(index)
    error('acousticbench:feedbackPath:emptySelection', ...
        'Selection %s = [%s] is empty.', argumentName, num2str(wanted));
end
end
