function T = thresholdTable(data, options)
%THRESHOLDTABLE Tidy threshold table per device and audiometric frequency.
%
%   T = acousticbench.thresholdTable(DATA) returns a table with one row per
%   (device code, audiometric frequency).  Thresholds are hearing-aid
%   receiver voltages at threshold in dBV (container M_thr_ha); the table
%   summarises the subjects and reinsertions with the requested statistic.
%
%   T = acousticbench.thresholdTable(DATA, 'Name', VALUE, ...)
%
%   Name-Value arguments
%       'Statistic'   'median' (default) | 'mean'
%       'DeviceCodes' subset of 1..14 (default all)
%       'Frequencies' subset of the audiometric frequencies (default all)
%
%   Columns
%       DeviceCode, Family, FamilyLabel, Condition, FrequencyHz,
%       ValueDbv, NValid
%
%   Invalid (NaN) thresholds are excluded and never imputed.
%
%   Example
%       data = acousticbench.loadData('Data.mat');
%       T = acousticbench.thresholdTable(data, 'DeviceCodes', [2 4 6 8]);
%       head(T)
%
%   See also acousticbench.ptpe, acousticbench.loadData.

arguments
    data struct
    options.Statistic {mustBeTextScalar} = 'median'
    options.DeviceCodes double = []
    options.Frequencies double = []
end

statistic = validatestring(char(options.Statistic), {'median', 'mean'}, ...
    mfilename, 'Statistic');

deviceIndex = restrictIndex(1:numel(data.devices), options.DeviceCodes, 'DeviceCodes');
audiometric = data.audiometricFrequency;
frequencyIndex = 1:numel(audiometric);
if ~isempty(options.Frequencies)
    frequencyIndex = zeros(1, numel(options.Frequencies));
    for k = 1:numel(options.Frequencies)
        [distance, which] = min(abs(audiometric - options.Frequencies(k)));
        if distance > 1e-9
            error('acousticbench:thresholdTable:badFrequency', ...
                ['Frequency %g Hz is not an audiometric frequency; expected one of: %s.'], ...
                options.Frequencies(k), num2str(audiometric(:)'));
        end
        frequencyIndex(k) = which;
    end
    frequencyIndex = unique(frequencyIndex, 'stable');
end

threshold = data.variables.M_thr_ha;
valid = data.valid.M_thr_ha;
nDevice = numel(deviceIndex);
nFrequency = numel(frequencyIndex);
nRows = nDevice * nFrequency;

DeviceCode = zeros(nRows, 1);
Family = cell(nRows, 1);
FamilyLabel = cell(nRows, 1);
Condition = cell(nRows, 1);
FrequencyHz = zeros(nRows, 1);
ValueDbv = NaN(nRows, 1);
NValid = zeros(nRows, 1);

row = 0;
for d = 1:nDevice
    device = data.devices(deviceIndex(d));
    for f = 1:nFrequency
        row = row + 1;
        values = threshold(frequencyIndex(f), deviceIndex(d), :, :);
        values = values(isfinite(values) & valid(frequencyIndex(f), deviceIndex(d), :, :));
        DeviceCode(row) = device.code;
        Family{row} = device.family;
        FamilyLabel{row} = device.familyLabel;
        Condition{row} = device.condition;
        FrequencyHz(row) = audiometric(frequencyIndex(f));
        NValid(row) = numel(values);
        if ~isempty(values)
            if strcmp(statistic, 'median')
                ValueDbv(row) = median(values);
            else
                ValueDbv(row) = mean(values);
            end
        end
    end
end

T = table(DeviceCode, Family, FamilyLabel, Condition, FrequencyHz, ValueDbv, NValid);
end

% =======================================================================
function index = restrictIndex(index, wanted, argumentName)
if isempty(wanted)
    return;
end
wanted = unique(wanted(:)');
index = index(ismember(index, wanted));
if isempty(index)
    error('acousticbench:thresholdTable:emptySelection', ...
        'Selection %s = [%s] is empty.', argumentName, num2str(wanted));
end
end
