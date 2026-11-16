function result = wilcoxonTest(x, y, options)
%WILCOXONTEST Wilcoxon signed-rank test without the Statistics Toolbox.
%
%   RESULT = acousticbench.stats.wilcoxonTest(X, Y) tests the null
%   hypothesis that the paired differences D = X - Y are symmetrically
%   distributed around zero.  Zero differences are discarded (Wilcoxon's
%   original convention); tied absolute differences receive average ranks.
%
%   Name-Value arguments
%       'Alpha'  significance level (default 0.05)
%       'Tail'   'both' (default) | 'right' | 'left'
%
%   Output RESULT (struct)
%       n (non-zero differences), wPlus, wMinus, zStatistic, pValue,
%       effectSize (rank-biserial correlation), alpha, tail
%
%   The p-value uses the normal approximation with continuity correction
%   and the tie correction of the variance
%       Var(W+) = n(n+1)(2n+1)/24 - sum(t^3 - t)/48
%   over tie groups of size t.  This is an approximation: it is reliable
%   for n >= 10; for small samples it is conservative-liberal and is
%   reported as the normal approximation.
%
%   Example
%       d = (1:10)';
%       r = acousticbench.stats.wilcoxonTest(d, zeros(size(d)));
%       % all differences positive -> wMinus = 0, pValue < 0.01
%
%   Error identifiers: acousticbench:stats:badData,
%   acousticbench:stats:badTail, acousticbench:stats:noDifferences.
%
%   See also acousticbench.stats.pairedTTest, acousticbench.stats.rankBiserial.

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

differences = x - y;
differences = differences(differences ~= 0);
n = numel(differences);
if n < 2
    error('acousticbench:stats:noDifferences', ...
        'The signed-rank test requires at least two non-zero differences.');
end

[ranks, tieGroupSizes] = averageRanks(abs(differences));
wPlus = sum(ranks(differences > 0));
wMinus = sum(ranks(differences < 0));

meanW = n * (n + 1) / 4;
tieCorrection = sum(tieGroupSizes .^ 3 - tieGroupSizes) / 48;
varianceW = n * (n + 1) * (2 * n + 1) / 24 - tieCorrection;
if varianceW <= 0
    zStatistic = 0;
else
    deviation = wPlus - meanW;
    if deviation == 0
        zStatistic = 0;
    else
        zStatistic = (deviation - 0.5 * sign(deviation)) / sqrt(varianceW);
    end
end

normalUpperTail = 0.5 * erfc(zStatistic / sqrt(2));
switch tail
    case 'both'
        pValue = 2 * min(normalUpperTail, 1 - normalUpperTail);
    case 'right'
        pValue = normalUpperTail;
    otherwise
        pValue = 1 - normalUpperTail;
end
pValue = min(max(pValue, 0), 1);

totalRanks = n * (n + 1) / 2;
effectSize = (wPlus - wMinus) / totalRanks;

result = struct( ...
    'n', n, ...
    'wPlus', wPlus, ...
    'wMinus', wMinus, ...
    'zStatistic', zStatistic, ...
    'pValue', pValue, ...
    'effectSize', effectSize, ...
    'alpha', options.Alpha, ...
    'tail', tail);
end

% =======================================================================
function [ranks, groupSizes] = averageRanks(values)
values = values(:);
n = numel(values);
[sorted, order] = sort(values);
ranks = zeros(n, 1);
groupSizes = [];
i = 1;
while i <= n
    j = i;
    while j < n && sorted(j + 1) == sorted(i)
        j = j + 1;
    end
    averageRank = (i + j) / 2;
    ranks(order(i:j)) = averageRank;
    groupSizes(end + 1) = j - i + 1; %#ok<AGROW>
    i = j + 1;
end
end
