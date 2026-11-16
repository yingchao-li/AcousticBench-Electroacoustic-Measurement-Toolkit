function refs = referenceMetrics(data, options)
%REFERENCEMETRICS Dataset reference rows for the E15 cross-language check.
%
%   REFS = acousticbench.referenceMetrics(DATA) returns a 1x142 struct array
%   with the fields
%       testId    cross-language test identifier (see below)
%       quantity  quantity name
%       value     scalar value (NaN if no valid observation)
%       unit      'dB' or '%'
%
%   The rows are exactly the dataset part of the E15 contract consumed by
%   results/validation/matlab_reference.csv (header
%   test_id,quantity,value,unit).  Octave-band definitions come from
%   acousticbench.octaveBands with centres
%   63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000 Hz (edges
%   centre/sqrt(2) and centre*sqrt(2); bins with low <= f < high; power
%   averaging in acousticbench.bandLevels).
%
%   Hha octave-band levels (36 rows)
%       test_id   'hha_band:<device_code>:<band_center_hz>'
%       quantity  'hha_band_db', unit 'dB'
%       For each earmold measurement code (2, 4, 6, 8) separately: Hha in
%       dB SPL from M_ha2edR, measurement condition, octave-band level,
%       median over all valid subject x reinsertion observations.  NaNs
%       and structurally invalid entries are excluded, never imputed.
%
%   REOIG octave-band levels (63 rows)
%       test_id   'reoig_band:<family>:<band_center_hz>'
%       quantity  'reoig_db', unit 'dB'
%       For each of the seven families, using its measurement-condition
%       device code: the octave-band level of M_ls2edM minus the octave-band
%       level of M_REUR, i.e. 10 log10(mean band power of M_ls2edM /
%       mean band power of M_REUR).  This is a ratio of mean band powers, NOT
%       the mean of the pointwise dB ratios.  The arbitrary free-field
%       storage scaling cancels in the difference.  Median over all valid
%       subject x reinsertion observations.
%
%   PTPE delta-Hha octave-band levels (36 rows)
%       test_id   'ptpe_hha_band:<family>:<band_center_hz>'
%       quantity  'ptpe_hha_db', unit 'dB'
%       For the four earmold families: Delta Hha band level =
%       band level(M_ha2edR, measurement code)
%       - band level(M_ha2edR, reference code), median over
%       subjects/reinsertions.
%
%   PTPE delta-threshold at 125 Hz (7 rows)
%       test_id   'delta_t_125:<family>'
%       quantity  'delta_t_db', unit 'dB'
%       Delta T = T_ref - T_meas at 125 Hz (audiometric grid) for all seven
%       families, median over subjects/reinsertions.
%
%   Name-Value arguments
%       'BandCenters'  octave-band centres (default
%                      [63 125 250 500 1000 2000 4000 8000 16000])
%
%   Example
%       data = acousticbench.loadData('Data.mat');
%       refs = acousticbench.referenceMetrics(data);
%       fprintf('%s = %.6f %s\n', refs(1).testId, refs(1).value, refs(1).unit);
%
%   See also acousticbench.hha, acousticbench.reoig, acousticbench.ptpe,
%   acousticbench.bandLevels, run_cross_language_export.

arguments
    data struct
    options.BandCenters double = [63 125 250 500 1000 2000 4000 8000 16000]
end

bands = acousticbench.octaveBands('Centers', options.BandCenters(:)');
nBands = numel(bands);
refs = repmat(struct('testId', '', 'quantity', '', 'value', NaN, 'unit', ''), 1, 0);

earmoldMeasurementCodes = [2, 4, 6, 8];
earmoldFamilies = {'closed_earmold', 'vented_earmold', 'nugget_earmold', 'silicone_earmold'};
families = unique({data.devices.family}, 'stable');

%% Hha octave-band levels, per earmold measurement device code -----------
for code = earmoldMeasurementCodes
    levels = acousticbench.hha(data, 'Container', 'M_ha2edR', ...
        'Condition', 'measurement', 'DeviceCodes', code);
    bandDb = acousticbench.bandLevels(levels, data.frequency, bands);
    for b = 1:nBands
        refs(end + 1) = makeRow( ... %#ok<AGROW>
            sprintf('hha_band:%d:%g', code, bands(b).centerHz), ...
            'hha_band_db', medianFinite(reshape(bandDb(b, :, :, :), [], 1)), 'dB');
    end
end

%% REOIG octave-band levels, per family (measurement condition) ----------
% Band levels of numerator and denominator are formed separately in the
% power domain and then subtracted: ratio of mean band powers.
nSubject = numel(data.subjects);
openPressure = data.variables.M_REUR;
openLevels = 20 * log10(max(abs(openPressure), 1e-10));
openLevels(~data.valid.M_REUR) = NaN;
openBand = acousticbench.bandLevels(openLevels, data.frequency, bands);  % nBand x nSubject
openBand = reshape(openBand, [nBands, 1, nSubject, 1]);
for k = 1:numel(families)
    family = families{k};
    code = measurementCodeOf(data, family);
    occludedPressure = data.variables.M_ls2edM(:, code, :, :);
    occludedValid = data.valid.M_ls2edM(:, code, :, :);
    occludedLevels = 20 * log10(max(abs(occludedPressure), 1e-10));
    occludedLevels(~occludedValid) = NaN;
    occludedBand = acousticbench.bandLevels(occludedLevels, data.frequency, bands);
    deltaBand = occludedBand - openBand;
    for b = 1:nBands
        refs(end + 1) = makeRow( ... %#ok<AGROW>
            sprintf('reoig_band:%s:%g', family, bands(b).centerHz), ...
            'reoig_db', medianFinite(reshape(deltaBand(b, :, :, :), [], 1)), 'dB');
    end
end

%% PTPE delta-Hha octave-band levels, per earmold family -----------------
for k = 1:numel(earmoldFamilies)
    family = earmoldFamilies{k};
    [referenceCode, measurementCode] = codesOf(data, family);
    referenceLevels = acousticbench.hha(data, 'Container', 'M_ha2edR', ...
        'Condition', 'all', 'DeviceCodes', referenceCode);
    measurementLevels = acousticbench.hha(data, 'Container', 'M_ha2edR', ...
        'Condition', 'all', 'DeviceCodes', measurementCode);
    referenceBand = acousticbench.bandLevels(referenceLevels, data.frequency, bands);
    measurementBand = acousticbench.bandLevels(measurementLevels, data.frequency, bands);
    deltaBand = measurementBand - referenceBand;
    for b = 1:nBands
        refs(end + 1) = makeRow( ... %#ok<AGROW>
            sprintf('ptpe_hha_band:%s:%g', family, bands(b).centerHz), ...
            'ptpe_hha_db', medianFinite(reshape(deltaBand(b, :, :, :), [], 1)), 'dB');
    end
end

%% PTPE delta-threshold at 125 Hz, per family ----------------------------
for k = 1:numel(families)
    family = families{k};
    out = acousticbench.ptpe(data, family, 'Metric', 'threshold', ...
        'Frequencies', 125);
    refs(end + 1) = makeRow( ... %#ok<AGROW>
        sprintf('delta_t_125:%s', family), ...
        'delta_t_db', out.medianDb(1), 'dB');
end
end

% =======================================================================
function code = measurementCodeOf(data, family)
devices = data.devices;
match = strcmp({devices.family}, family) & [devices.isMeasurement];
if ~any(match)
    error('acousticbench:referenceMetrics:noMeasurementCode', ...
        'Family "%s" has no measurement device code.', family);
end
code = devices(find(match, 1)).code;
end

% =======================================================================
function [referenceCode, measurementCode] = codesOf(data, family)
devices = data.devices;
match = strcmp({devices.family}, family);
codes = [devices(match).code];
referenceCode = min(codes);
measurementCode = max(codes);
if mod(referenceCode, 2) == 0 || measurementCode ~= referenceCode + 1
    error('acousticbench:referenceMetrics:badFamily', ...
        'Family "%s" does not map to a reference/measurement code pair.', family);
end
end

% =======================================================================
function row = makeRow(testId, quantity, value, unit)
row = struct('testId', testId, 'quantity', quantity, 'value', value, 'unit', unit);
end

% =======================================================================
function value = medianFinite(values)
values = values(isfinite(values));
if isempty(values)
    value = NaN;
else
    value = median(values);
end
end
