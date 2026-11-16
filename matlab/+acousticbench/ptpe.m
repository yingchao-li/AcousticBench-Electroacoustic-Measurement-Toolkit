function out = ptpe(data, family, options)
%PTPE Probe-tube presence effect (PTPE) for one earpiece family.
%
%   OUT = acousticbench.ptpe(DATA, FAMILY) computes the probe-tube presence
%   effect for the hearing-aid driver response of FAMILY, i.e. the change
%   between the measurement condition (probe tube additionally inserted)
%   and the reference condition:
%
%       deltaHha(f) = Hha_meas(f) - Hha_ref(f)     [dB]
%
%   OUT = acousticbench.ptpe(DATA, FAMILY, 'Metric', METRIC, ...) selects
%   the metric:
%
%       'hha'        Hha(RPT, measurement) - Hha(RPT, reference)
%                    (earmolds only; the reference probe tube exists only
%                    for earmolds)
%       'reoig'      REOIG(measurement) - REOIG(reference)
%                    (earmolds only)
%       'threshold'  deltaT = T_ref - T_meas at the audiometric
%                    frequencies (all families; a negative value means the
%                    receiver needed a higher voltage at threshold with the
%                    probe tube inserted)
%
%   Name-Value arguments
%       'Metric'       'hha' (default) | 'reoig' | 'threshold'
%       'Frequencies'  evaluation frequencies [Hz].  For 'hha'/'reoig' the
%                      DFT bin nearest to each requested frequency is used;
%                      default [100 250 500 1000].  For 'threshold' the
%                      requested frequency must be one of the audiometric
%                      frequencies (125 250 500 750 1000 2000); default 125.
%       'Subjects'     subset of 1..14 (default all)
%       'Reinsertions' subset of 1..3 (default all)
%
%   Output OUT (struct)
%       metric, family, familyLabel, deviceCodes (= [reference measurement])
%       frequenciesHz   nFreq x 1 selected frequencies [Hz]
%       delta           nFreq x nSubject x nReinsertion double (NaN invalid)
%       nValid          number of finite delta entries
%       medianDb        nFreq x 1 median across subjects/reinsertions
%       meanDb          nFreq x 1 mean across subjects/reinsertions
%       nValidPerFrequency  nFreq x 1
%
%   Example
%       data = acousticbench.loadData('Data.mat');
%       out = acousticbench.ptpe(data, 'closed_earmold', 'Metric', 'hha');
%       disp([out.frequenciesHz out.medianDb])
%
%   Error identifiers: acousticbench:ptpe:notEarmold,
%   acousticbench:ptpe:badFrequency, acousticbench:ptpe:unknownFamily.
%
%   See also acousticbench.hha, acousticbench.reoig.

arguments
    data struct
    family {mustBeTextScalar}
    options.Metric {mustBeTextScalar} = 'hha'
    options.Frequencies double = []
    options.Subjects double = []
    options.Reinsertions double = []
end

metric = validatestring(char(options.Metric), ...
    {'hha', 'reoig', 'threshold'}, mfilename, 'Metric');

families = unique({data.devices.family});
family = validatestring(char(family), families, mfilename, 'family');
familyDevices = data.devices(strcmp({data.devices.family}, family));
if numel(familyDevices) ~= 2
    error('acousticbench:ptpe:unknownFamily', ...
        'Family "%s" does not map to a reference/measurement pair.', family);
end
refCode = familyDevices(1).code;
if mod(refCode, 2) == 0
    refCode = familyDevices(2).code;
end
measCode = refCode + 1;

subjectIndex = restrictIndex(1:numel(data.subjects), options.Subjects, 'Subjects');
reinsertionIndex = restrictIndex(1:numel(data.reinsertions), options.Reinsertions, 'Reinsertions');
nSubject = numel(subjectIndex);
nReinsertion = numel(reinsertionIndex);

if ~strcmp(metric, 'threshold') && ~familyDevices(1).isEarmold
    error('acousticbench:ptpe:notEarmold', ...
        ['Metric "%s" is not defined for family "%s": the reference probe ' ...
         'tube was used with earmolds only. Use Metric=''threshold'' for domes.'], ...
        metric, family);
end

switch metric
    case 'hha'
        frequencies = defaultFrequencies(options.Frequencies, [100 250 500 1000]);
        refLevels = acousticbench.hha(data, 'Container', 'M_ha2edR', ...
            'DeviceCodes', refCode, 'Subjects', subjectIndex, ...
            'Reinsertions', reinsertionIndex);
        measLevels = acousticbench.hha(data, 'Container', 'M_ha2edR', ...
            'DeviceCodes', measCode, 'Subjects', subjectIndex, ...
            'Reinsertions', reinsertionIndex);
        binIndex = nearestBins(data.frequency, frequencies);
        delta = reshape(measLevels(binIndex, :, :, :) - refLevels(binIndex, :, :, :), ...
            [numel(binIndex), nSubject, nReinsertion]);
    case 'reoig'
        frequencies = defaultFrequencies(options.Frequencies, [100 250 500 1000]);
        refGain = acousticbench.reoig(data, 'Condition', 'reference', ...
            'DeviceCodes', refCode, 'Subjects', subjectIndex, ...
            'Reinsertions', reinsertionIndex);
        measGain = acousticbench.reoig(data, 'Condition', 'measurement', ...
            'DeviceCodes', measCode, 'Subjects', subjectIndex, ...
            'Reinsertions', reinsertionIndex);
        binIndex = nearestBins(data.frequency, frequencies);
        delta = reshape(measGain(binIndex, :, :, :) - refGain(binIndex, :, :, :), ...
            [numel(binIndex), nSubject, nReinsertion]);
    otherwise
        frequencies = defaultFrequencies(options.Frequencies, 125);
        audiometric = data.audiometricFrequency;
        binIndex = nearestBins(audiometric, frequencies);
        threshold = data.variables.M_thr_ha;
        valid = data.valid.M_thr_ha;
        refValues = threshold(binIndex, refCode, subjectIndex, reinsertionIndex);
        measValues = threshold(binIndex, measCode, subjectIndex, reinsertionIndex);
        refValid = valid(binIndex, refCode, subjectIndex, reinsertionIndex);
        measValid = valid(binIndex, measCode, subjectIndex, reinsertionIndex);
        delta = refValues - measValues;
        delta(~(refValid & measValid)) = NaN;
end

frequenciesHz = frequencies(:);
nFrequency = numel(frequenciesHz);
delta = reshape(delta, [nFrequency, nSubject, nReinsertion]);

medianDb = NaN(nFrequency, 1);
meanDb = NaN(nFrequency, 1);
nValidPerFrequency = zeros(nFrequency, 1);
for f = 1:nFrequency
    values = reshape(delta(f, :, :), [], 1);
    values = values(isfinite(values));
    nValidPerFrequency(f) = numel(values);
    if ~isempty(values)
        medianDb(f) = median(values);
        meanDb(f) = mean(values);
    end
end

out = struct( ...
    'metric', metric, ...
    'family', family, ...
    'familyLabel', familyDevices(1).familyLabel, ...
    'deviceCodes', [refCode, measCode], ...
    'frequenciesHz', frequenciesHz, ...
    'delta', delta, ...
    'nValid', nnz(isfinite(delta)), ...
    'medianDb', medianDb, ...
    'meanDb', meanDb, ...
    'nValidPerFrequency', nValidPerFrequency);
end

% =======================================================================
function frequencies = defaultFrequencies(requested, fallback)
if isempty(requested)
    frequencies = fallback;
else
    frequencies = requested(:)';
end
end

% =======================================================================
function index = nearestBins(axisValues, requested)
index = zeros(1, numel(requested));
axisValues = axisValues(:)';
for k = 1:numel(requested)
    [distance, which] = min(abs(axisValues - requested(k)));
    if ~isfinite(distance)
        error('acousticbench:ptpe:badFrequency', ...
            'Cannot evaluate the requested frequency %g Hz.', requested(k));
    end
    index(k) = which;
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
    error('acousticbench:ptpe:emptySelection', ...
        'Selection %s = [%s] is empty.', argumentName, num2str(wanted));
end
end
