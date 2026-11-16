function result = pairedTTest(x, y, options)
%PAIREDTTEST Paired-samples t-test without the Statistics Toolbox.
%
%   RESULT = acousticbench.stats.pairedTTest(X, Y) tests the null hypothesis
%   that the paired differences D = X - Y have zero mean.  X and Y must be
%   equal-length vectors (one value per statistical unit, typically the
%   per-subject effect).
%
%   RESULT = acousticbench.stats.pairedTTest(X, Y, 'Name', VALUE, ...)
%
%   Name-Value arguments
%       'Alpha'  significance level (default 0.05)
%       'Tail'   'both' (default) | 'right' | 'left'
%                'right' tests mean(X - Y) > 0, 'left' tests < 0.
%
%   Output RESULT (struct)
%       n, meanDifference, sdDifference, standardError, tStatistic, df,
%       pValue, ci (1x2 confidence interval of the mean difference),
%       effectSizeDz (meanDifference/sdDifference), alpha, tail
%
%   The p-value uses the exact Student t distribution through the
%   regularized incomplete beta function (betainc), which is part of base
%   MATLAB; no toolbox is required.
%
%   Example
%       d = [1 2 3 4 5];
%       r = acousticbench.stats.pairedTTest(d, zeros(size(d)));
%       % r.tStatistic = 4.2426, r.pValue = 0.0132
%
%   Error identifiers: acousticbench:stats:badData,
%   acousticbench:stats:badAlpha, acousticbench:stats:badTail.
%
%   See also acousticbench.stats.wilcoxonTest, acousticbench.stats.cohensDz.

arguments
    x double
    y double
    options.Alpha (1,1) double = 0.05
    options.Tail {mustBeTextScalar} = 'both'
end

tail = validatestring(char(options.Tail), {'both', 'right', 'left'}, ...
    mfilename, 'Tail');
if options.Alpha <= 0 || options.Alpha >= 1
    error('acousticbench:stats:badAlpha', 'Alpha must lie strictly between 0 and 1.');
end
x = x(:);
y = y(:);
if isempty(x) || numel(x) ~= numel(y)
    error('acousticbench:stats:badData', ...
        'X and Y must be non-empty vectors of equal length.');
end
if numel(x) < 2
    error('acousticbench:stats:badData', ...
        'A paired t-test requires at least two pairs.');
end

differences = x - y;
n = numel(differences);
meanDifference = mean(differences);
sdDifference = std(differences, 0);
standardError = sdDifference / sqrt(n);
df = n - 1;

if standardError == 0
    if meanDifference == 0
        tStatistic = 0;
    else
        tStatistic = sign(meanDifference) * Inf;
    end
else
    tStatistic = meanDifference / standardError;
end

if ~isfinite(tStatistic)
    pValue = 0;
else
    twoSided = betainc(df / (df + tStatistic ^ 2), df / 2, 0.5);
    switch tail
        case 'both'
            pValue = twoSided;
        case 'right'
            if tStatistic >= 0
                pValue = twoSided / 2;
            else
                pValue = 1 - twoSided / 2;
            end
        otherwise
            if tStatistic <= 0
                pValue = twoSided / 2;
            else
                pValue = 1 - twoSided / 2;
            end
    end
end

if strcmp(tail, 'both')
    criticalValue = tInverse(1 - options.Alpha / 2, df);
else
    criticalValue = tInverse(1 - options.Alpha, df);
end
ci = meanDifference + [-1, 1] * criticalValue * standardError;

if sdDifference == 0
    effectSizeDz = NaN;
else
    effectSizeDz = meanDifference / sdDifference;
end

result = struct( ...
    'n', n, ...
    'meanDifference', meanDifference, ...
    'sdDifference', sdDifference, ...
    'standardError', standardError, ...
    'tStatistic', tStatistic, ...
    'df', df, ...
    'pValue', pValue, ...
    'ci', ci, ...
    'effectSizeDz', effectSizeDz, ...
    'alpha', options.Alpha, ...
    'tail', tail);
end

% =======================================================================
function t = tInverse(p, df)
% Inverse Student-t CDF for p in (0, 1) using betaincinv (base MATLAB).
if p <= 0 || p >= 1
    error('acousticbench:stats:badAlpha', 'tInverse requires 0 < p < 1.');
end
if abs(p - 0.5) < 1e-15
    t = 0;
    return;
end
if p < 0.5
    t = -tInverse(1 - p, df);
    return;
end
beta = 2 * (1 - p);
x = betaincinv(df / 2, 0.5, beta);
t = sqrt(df * (1 / x - 1));
end
