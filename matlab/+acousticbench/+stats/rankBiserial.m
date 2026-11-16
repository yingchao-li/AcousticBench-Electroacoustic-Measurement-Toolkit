function [r, info] = rankBiserial(x, y)
%RANKBISERIAL Rank-biserial correlation effect size for the signed-rank test.
%
%   R = acousticbench.stats.rankBiserial(X, Y) returns the rank-biserial
%   correlation of the paired differences D = X - Y, computed from the
%   Wilcoxon signed ranks:
%
%       r = (W+ - W-) / (n (n + 1) / 2)
%
%   Zero differences are discarded (Wilcoxon convention) and tied absolute
%   differences receive average ranks, exactly as in
%   acousticbench.stats.wilcoxonTest.  R ranges from -1 (all differences
%   negative) through 0 (symmetric ranks) to +1 (all differences positive).
%
%   [R, INFO] = ... also returns INFO with n (non-zero differences),
%   wPlus and wMinus.
%
%   Example
%       d = (1:10)';
%       r = acousticbench.stats.rankBiserial(d, zeros(size(d)));   % 1
%
%   Error identifiers: acousticbench:stats:badData,
%   acousticbench:stats:noDifferences.
%
%   See also acousticbench.stats.wilcoxonTest, acousticbench.stats.cohensDz.

arguments
    x double
    y double
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
if n < 1
    error('acousticbench:stats:noDifferences', ...
        'The rank-biserial correlation requires at least one non-zero difference.');
end

ranks = averageRanks(abs(differences));
wPlus = sum(ranks(differences > 0));
wMinus = sum(ranks(differences < 0));
totalRanks = n * (n + 1) / 2;
r = (wPlus - wMinus) / totalRanks;

info = struct('n', n, 'wPlus', wPlus, 'wMinus', wMinus);
end

% =======================================================================
function ranks = averageRanks(values)
values = values(:);
n = numel(values);
[sorted, order] = sort(values);
ranks = zeros(n, 1);
i = 1;
while i <= n
    j = i;
    while j < n && sorted(j + 1) == sorted(i)
        j = j + 1;
    end
    ranks(order(i:j)) = (i + j) / 2;
    i = j + 1;
end
end
