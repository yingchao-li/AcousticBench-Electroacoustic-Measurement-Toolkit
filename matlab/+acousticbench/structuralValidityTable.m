function T = structuralValidityTable(containerKey)
%STRUCTURALVALIDITYTABLE Tabulate structural validity per container/device.
%
%   T = acousticbench.structuralValidityTable() returns a 98x7 table
%   (7 containers x 14 device codes) that documents, for every container,
%   whether the stored value is physically meaningful for the device.
%
%   T = acousticbench.structuralValidityTable(KEY) restricts the table to
%   one container (KEY is one of the container names below).
%
%   Columns
%       Container          container / MAT variable name
%       DeviceCode         dataset device code 1..14
%       Family             machine-readable earpiece family
%       Coupling           'earmold' or 'dome'
%       Condition          'reference' or 'measurement'
%       StructurallyValid  logical; false = stored value is not the
%                          documented eardrum quantity and must be masked
%       Rationale          documented reason for the structural rule
%
%   Containers: M_ha2edM, M_ha2edR, M_ha2haf, M_ls2edM, M_ls2edR,
%               M_thr_ha, M_REUR
%
%   The rules are: M_*edM are meaningful only in the measurement condition
%   (the measurement probe tube hung loosely around the ear in the
%   reference condition); M_*edR are meaningful only for earmolds (the
%   reference probe tube was used with earmolds only); M_ha2haf, M_thr_ha
%   and M_REUR have no structural restriction.
%
%   Example
%       T = acousticbench.structuralValidityTable('M_ha2edR');
%       codes = T.DeviceCode(T.StructurallyValid)      % -> 1 2 3 4 5 6 7 8
%
%   See also acousticbench.loadData.

arguments
    containerKey {mustBeTextScalar} = ''
end

containers = {'M_ha2edM', 'M_ha2edR', 'M_ha2haf', 'M_ls2edM', 'M_ls2edR', ...
              'M_thr_ha', 'M_REUR'};
devices = acousticbench.deviceTable();

restrict = strlength(string(containerKey)) > 0;
if restrict
    containerKey = char(containerKey);
    if ~any(strcmp(containers, containerKey))
        error('acousticbench:structuralValidityTable:unknownContainer', ...
            'Unknown container "%s"; expected one of: %s.', ...
            containerKey, strjoin(containers, ', '));
    end
end

nDevices = numel(devices);
selected = containers;
if restrict
    selected = {containerKey};
end
rows = numel(selected) * nDevices;

Container = cell(rows, 1);
DeviceCode = zeros(rows, 1);
Family = cell(rows, 1);
Coupling = cell(rows, 1);
Condition = cell(rows, 1);
StructurallyValid = false(rows, 1);
Rationale = cell(rows, 1);

row = 0;
for k = 1:numel(selected)
    key = selected{k};
    structural = structuralMaskFor(key, devices);
    rationale = rationaleFor(key);
    for d = 1:nDevices
        row = row + 1;
        Container{row} = key;
        DeviceCode(row) = devices(d).code;
        Family{row} = devices(d).family;
        Coupling{row} = devices(d).coupling;
        Condition{row} = devices(d).condition;
        StructurallyValid(row) = structural(d);
        Rationale{row} = rationale;
    end
end

T = table(Container, DeviceCode, Family, Coupling, Condition, ...
    StructurallyValid, Rationale);
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
function text = rationaleFor(key)
switch key
    case 'M_ha2edM'
        text = ['Measurement probe tube; in the reference condition the tube ' ...
                'hung loosely around the ear, so the value is not an eardrum pressure.'];
    case 'M_ha2edR'
        text = ['Reference probe tube; used only with earmolds, so dome values ' ...
                'are not eardrum pressures.'];
    case 'M_ha2haf'
        text = 'Hearing-aid microphone: part of the device and always present.';
    case 'M_ls2edM'
        text = ['Loudspeaker drive with the measurement probe tube; the reference ' ...
                'condition value measures the free field, not the eardrum.'];
    case 'M_ls2edR'
        text = ['Loudspeaker drive with the reference probe tube; available for ' ...
                'earmolds only.'];
    case 'M_thr_ha'
        text = 'Behavioural threshold with the hearing-aid driver; no structural restriction.';
    case 'M_REUR'
        text = 'Open-ear unaided response; measured once per participant.';
    otherwise
        text = '';
end
end
