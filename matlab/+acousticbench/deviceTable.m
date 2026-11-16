function devices = deviceTable()
%DEVICETABLE Metadata for the 14 device/condition codes of the dataset.
%
%   DEVICES = acousticbench.deviceTable() returns a 1x14 struct array that
%   mirrors the device axis (Dim 2) of the AcousticBench data containers.
%   Dim 2 = device code 1..14 = 7 earpiece families x {reference,
%   measurement} probe condition.  Odd codes are the reference condition,
%   even codes the measurement condition; codes 1..8 are earmolds, 9..14
%   are domes.
%
%   Fields (per element)
%       code            device code 1..14
%       family          machine-readable family, e.g. 'closed_earmold'
%       familyLabel     human-readable family, e.g. 'Closed Earmold'
%       coupling        'earmold' (codes 1..8) or 'dome' (codes 9..14)
%       condition       'reference' (odd) or 'measurement' (even)
%       label           full label, e.g. 'Closed Earmold - Measurement'
%       shortLabel      compact label, e.g. 'Closed/Meas'
%       isReference     true for odd codes
%       isMeasurement   true for even codes
%       isEarmold       true for codes 1..8
%       isDome          true for codes 9..14
%       pairCode        the other condition of the same family
%
%   Example
%       d = acousticbench.deviceTable();
%       codes = [d(d.isEarmold & d.isMeasurement).code]   % -> 2 4 6 8
%
%   See also acousticbench.constants, acousticbench.loadData.

families = { ...
    'closed_earmold',   'Closed Earmold',   'Closed'; ...
    'vented_earmold',   'Vented Earmold',   'Vented'; ...
    'nugget_earmold',   'Nugget Earmold',   'Nugget'; ...
    'silicone_earmold', 'Silicone Earmold', 'Silicone'; ...
    'open_dome',        'Open Dome',        'Open'; ...
    'tulip_dome',       'Tulip Dome',       'Tulip'; ...
    'power_dome',       'Power Dome',       'Power'};

template = struct( ...
    'code', 0, ...
    'family', '', ...
    'familyLabel', '', ...
    'coupling', '', ...
    'condition', '', ...
    'label', '', ...
    'shortLabel', '', ...
    'isReference', false, ...
    'isMeasurement', false, ...
    'isEarmold', false, ...
    'isDome', false, ...
    'pairCode', 0);
devices = repmat(template, 1, 14);

for code = 1:14
    familyIndex = floor((code - 1) / 2) + 1;
    isReference = mod(code, 2) == 1;
    d = template;
    d.code = code;
    d.family = families{familyIndex, 1};
    d.familyLabel = families{familyIndex, 2};
    if code <= 8
        d.coupling = 'earmold';
        d.isEarmold = true;
    else
        d.coupling = 'dome';
        d.isDome = true;
    end
    if isReference
        d.condition = 'reference';
        d.isReference = true;
        d.shortLabel = sprintf('%s/Ref', families{familyIndex, 3});
        d.label = sprintf('%s - Reference', d.familyLabel);
        d.pairCode = code + 1;
    else
        d.condition = 'measurement';
        d.isMeasurement = true;
        d.shortLabel = sprintf('%s/Meas', families{familyIndex, 3});
        d.label = sprintf('%s - Measurement', d.familyLabel);
        d.pairCode = code - 1;
    end
    devices(code) = d;
end
end
