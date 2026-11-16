function [levelsDb, bandInfo] = bandLevels(valuesDb, freqHz, bands, options)
%BANDLEVELS Power-average band levels from narrowband dB values.
%
%   LEVELSDB = acousticbench.bandLevels(VALUESDB, FREQHZ, BANDS) averages
%   narrowband dB values within each frequency band using a power average:
%
%       L_band = 10 log10( mean_{f in band} 10^(L(f)/10) )
%
%   which is the correct operation for transfer-function levels.  For a
%   ratio quantity such as REOIG, apply this function separately to the
%   numerator and denominator levels and subtract (as
%   acousticbench.referenceMetrics does); averaging the pointwise dB ratios
%   would instead estimate a mean of ratios, which is a different estimator.
%   NaN entries are excluded from the average and are never imputed; a band
%   with no finite bin yields NaN.
%
%   Inputs
%       VALUESDB  nFreq x ... double array of dB values (real)
%       FREQHZ    nFreq x 1 frequency axis [Hz]
%       BANDS     struct array from acousticbench.octaveBands,
%                 acousticbench.thirdOctaveBands or a compatible struct
%                 with fields label, centerHz, lowHz, highHz.
%                 Bin selection: lowHz <= f < highHz.
%
%   Name-Value arguments
%       'FloorDb'  power floor in dB applied per bin (default -200)
%
%   Outputs
%       LEVELSDB  nBands x ... double band levels (NaN where no finite bin)
%       BANDINFO  struct array copy of BANDS extended with a field nBins
%
%   Example
%       data = acousticbench.loadData('Data.mat');
%       L = acousticbench.hha(data);
%       bands = acousticbench.octaveBands('Centers', [500 1000]);
%       bandDb = acousticbench.bandLevels(L, data.frequency, bands);
%
%   See also acousticbench.octaveBands, acousticbench.thirdOctaveBands,
%   acousticbench.hha.

arguments
    valuesDb double
    freqHz double
    bands struct
    options.FloorDb (1,1) double = -200
end

freqHz = freqHz(:);
if numel(freqHz) ~= size(valuesDb, 1)
    error('acousticbench:bandLevels:sizeMismatch', ...
        'FREQHZ has %d entries but VALUESDB has %d rows.', ...
        numel(freqHz), size(valuesDb, 1));
end
requiredFields = {'label', 'centerHz', 'lowHz', 'highHz'};
if ~all(isfield(bands, requiredFields))
    error('acousticbench:bandLevels:badBands', ...
        'BANDS must have the fields label, centerHz, lowHz and highHz.');
end

sizes = size(valuesDb);
nBands = numel(bands);
outSize = [nBands, sizes(2:end)];
levelsDb = NaN(outSize);

floorPower = 10 ^ (options.FloorDb / 10);
bandInfo = bands;
for b = 1:nBands
    mask = freqHz >= bands(b).lowHz & freqHz < bands(b).highHz;
    bandInfo(b).nBins = nnz(mask);
    if ~any(mask)
        continue;
    end
    block = reshape(valuesDb(mask, :), [nnz(mask), sizes(2:end)]);
    power = 10 .^ (block / 10);
    % Clamp only non-NaN values; NaN must stay NaN (no imputation).
    power(power < floorPower) = floorPower;
    averagePower = nanMean(power, 1);
    levelsDb(b, :) = reshape(10 * log10(averagePower), [1, outSize(2:end)]);
end
end

% =======================================================================
function m = nanMean(x, dim)
finite = isfinite(x);
counts = sum(finite, dim);
x(~finite) = 0;
totals = sum(x, dim);
m = totals ./ counts;
m(counts == 0) = NaN;
end
