function [ci, bootstrapStats] = bootstrapCI(data, statisticFcn, nResamples, seed, options)
%BOOTSTRAPCI Percentile bootstrap confidence interval (subject as unit).
%
%   CI = acousticbench.stats.bootstrapCI(DATA, STATISTICFCN, NRESAMPLES,
%   SEED) resamples the rows of DATA with replacement (one row = one
%   statistical unit, normally one subject) and returns the percentile
%   bootstrap confidence interval of STATISTICFCN applied to the resampled
%   matrix.
%
%   [CI, BOOTSTRAPSTATS] = ... also returns the NRESAMPLES x 1 bootstrap
%   statistics.
%
%   Inputs
%       DATA          nUnits x nVariables double matrix (rows are resampled)
%       STATISTICFCN  handle to a function returning a scalar from a
%                     matriX with the same number of columns as DATA,
%                     e.g. @(x) mean(x(:, 1))
%       NRESAMPLES    number of bootstrap resamples (e.g. 10000)
%       SEED          integer seed for the local mt19937ar stream; the
%                     result is deterministic, no global RNG state is used
%
%   Name-Value arguments
%       'Alpha'  significance level (default 0.05 -> 95 % interval)
%
%   The percentile interval is computed with linear interpolation between
%   order statistics (the numpy/pandas default), i.e. for n resamples the
%   p-quantile is evaluated at position p*(n-1)+1.
%
%   Example
%       data = (1:14)';
%       ci = acousticbench.stats.bootstrapCI(data, @(x) mean(x(:, 1)), 2000, 20260422);
%
%   Error identifiers: acousticbench:stats:badData,
%   acousticbench:stats:badStatistic, acousticbench:stats:badAlpha.
%
%   See also acousticbench.stats.pairedTTest.

arguments
    data double
    statisticFcn function_handle
    nResamples (1,1) double {mustBeInteger, mustBePositive}
    seed (1,1) double {mustBeInteger} = 20260422
    options.Alpha (1,1) double = 0.05
end

if options.Alpha <= 0 || options.Alpha >= 1
    error('acousticbench:stats:badAlpha', 'Alpha must lie strictly between 0 and 1.');
end
if isempty(data) || ~ismatrix(data)
    error('acousticbench:stats:badData', 'DATA must be a non-empty 2-D matrix.');
end
nUnits = size(data, 1);
if nUnits < 2
    error('acousticbench:stats:badData', ...
        'The bootstrap requires at least two statistical units (rows).');
end

stream = RandStream('mt19937ar', 'Seed', seed);
bootstrapStats = zeros(nResamples, 1);
for b = 1:nResamples
    indices = randi(stream, nUnits, 1);
    value = statisticFcn(data(indices, :));
    if ~isscalar(value) || ~isnumeric(value) || ~isfinite(value)
        error('acousticbench:stats:badStatistic', ...
            'STATISTICFCN must return a finite numeric scalar (resample %d).', b);
    end
    bootstrapStats(b) = value;
end

ci = [percentile(bootstrapStats, options.Alpha / 2), ...
      percentile(bootstrapStats, 1 - options.Alpha / 2)];
end

% =======================================================================
function q = percentile(values, p)
values = sort(values(:));
n = numel(values);
if n == 1
    q = values(1);
    return;
end
position = p * (n - 1) + 1;
lowerIndex = floor(position);
upperIndex = ceil(position);
fraction = position - lowerIndex;
if lowerIndex < 1
    lowerIndex = 1;
end
if upperIndex > n
    upperIndex = n;
end
q = (1 - fraction) * values(lowerIndex) + fraction * values(upperIndex);
end
