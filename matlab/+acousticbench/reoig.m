function [reoigDb, freqHz, info] = reoig(data, options)
%REOIG Real-ear occluded insertion gain in dB.
%
%   [REOIGDB, FREQHZ] = acousticbench.reoig(DATA) returns the real-ear
%   occluded insertion gain (REOIG) in dB for the measurement condition:
%
%       REOIG(f) = 20 log10(|M_ls2edM(f)|) - 20 log10(|M_REUR(f)|)
%
%   which is the power-consistent ratio of the loudspeaker-driven eardrum
%   pressure with the earpiece in place to the open-ear (unaided) response
%   of the same subject.  The arbitrary free-field scaling of the stored
%   loudspeaker data cancels in the ratio.
%
%   [REOIGDB, FREQHZ] = acousticbench.reoig(DATA, 'Name', VALUE, ...)
%   controls the probe condition and selection.
%
%   Name-Value arguments
%       'Condition'    'measurement' (default) or 'reference'
%                      'measurement': M_ls2edM, codes 2 4 6 8 10 12 14
%                      'reference'  : M_ls2edR, earmold codes 1 3 5 7
%                                     (reference probe used with earmolds only)
%       'DeviceCodes'  subset of 1..14 (default all structurally valid)
%       'Subjects'     subset of 1..14 (default all)
%       'Reinsertions' subset of 1..3 (default all)
%       'FloorDb'      magnitude floor in dB (default -200)
%
%   Outputs
%       REOIGDB   nFreq x nDevice x nSubject x nReinsertion double, NaN
%                 where invalid (measured NaN or structurally invalid)
%       FREQHZ    nFreq x 1 frequency axis [Hz]
%       INFO      struct with condition, container, device codes, counts
%
%   Example
%       data = acousticbench.loadData('Data.mat');
%       G = acousticbench.reoig(data, 'Condition', 'measurement');
%       bandLevel = acousticbench.bandLevels(G, data.frequency, ...
%           acousticbench.octaveBands('Centers', 1000));
%
%   Error identifiers: acousticbench:reoig:emptySelection.
%
%   See also acousticbench.hha, acousticbench.ptpe, acousticbench.bandLevels.

arguments
    data struct
    options.Condition {mustBeTextScalar} = 'measurement'
    options.DeviceCodes double = []
    options.Subjects double = []
    options.Reinsertions double = []
    options.FloorDb (1,1) double = -200
end

condition = validatestring(char(options.Condition), ...
    {'measurement', 'reference'}, mfilename, 'Condition');

if strcmp(condition, 'measurement')
    container = 'M_ls2edM';
else
    container = 'M_ls2edR';
end

% Device selection: condition first, then structural validity, then codes.
deviceIndex = 1:numel(data.devices);
conditionMask = arrayfun(@(d) strcmp(d.condition, condition), data.devices);
deviceIndex = deviceIndex(conditionMask);
structuralMask = reshape(data.structural.(container), 1, []);
deviceIndex = deviceIndex(structuralMask(deviceIndex));
deviceIndex = restrictIndex(deviceIndex, options.DeviceCodes, 'DeviceCodes');

subjectIndex = restrictIndex(1:numel(data.subjects), options.Subjects, 'Subjects');
reinsertionIndex = restrictIndex(1:numel(data.reinsertions), options.Reinsertions, 'Reinsertions');

nFrequency = numel(data.frequency);
nSubject = numel(subjectIndex);

numerator = data.variables.(container);
numeratorValid = data.valid.(container);
numerator = numerator(:, deviceIndex, subjectIndex, reinsertionIndex);
numeratorValid = numeratorValid(:, deviceIndex, subjectIndex, reinsertionIndex);

reur = data.variables.M_REUR;
reurValid = data.valid.M_REUR;
reur = reshape(reur(:, subjectIndex), nFrequency, 1, nSubject, 1);
reurValid = reshape(reurValid(:, subjectIndex), nFrequency, 1, nSubject, 1);

floorAmplitude = 10 ^ (options.FloorDb / 20);
numeratorMagnitude = max(abs(numerator), floorAmplitude);
denominatorMagnitude = max(abs(reur), floorAmplitude);

reoigDb = 20 * log10(numeratorMagnitude) - 20 * log10(denominatorMagnitude);
reoigDb(~(numeratorValid & reurValid)) = NaN;

freqHz = data.frequency;

if nargout > 2
    info = struct( ...
        'condition', condition, ...
        'container', container, ...
        'deviceCodes', [data.devices(deviceIndex).code], ...
        'subjects', data.subjects(subjectIndex)', ...
        'reinsertions', data.reinsertions(reinsertionIndex)', ...
        'nValid', nnz(isfinite(reoigDb)));
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
    error('acousticbench:reoig:emptySelection', ...
        'Selection %s = [%s] is empty.', argumentName, num2str(wanted));
end
end
