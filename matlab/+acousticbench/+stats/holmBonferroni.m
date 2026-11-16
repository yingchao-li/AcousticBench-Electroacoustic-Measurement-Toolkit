function [adjustedP, rejected] = holmBonferroni(pValues, alpha)
%HOLMBONFERRONI Holm-Bonferroni step-down multiple-comparison correction.
%
%   [ADJUSTEDP, REJECTED] = acousticbench.stats.holmBonferroni(PVALUES)
%   adjusts a vector of p-values with the Holm-Bonferroni method and
%   returns the adjusted p-values in the original order plus the rejection
%   decision at ALPHA (default 0.05).
%
%   Inputs
%       PVALUES  numeric vector of p-values in [0, 1]; NaN entries are
%                ignored and returned as NaN (not significant)
%       ALPHA    significance level (default 0.05)
%
%   Method
%       With m finite p-values sorted ascending p_(1) <= ... <= p_(m),
%       adjusted_(i) = min(1, max_{j <= i} (m - j + 1) * p_(j)),
%       enforcing monotonicity; the step-down rejection rule is equivalent
%       to adjusted <= ALPHA.
%
%   Example
%       p = [0.01 0.04 0.03 0.005];
%       [adj, rej] = acousticbench.stats.holmBonferroni(p);
%       % adj = [0.03 0.06 0.06 0.02], all rejected at alpha = 0.05
%
%   Error identifiers: acousticbench:stats:badPValues,
%   acousticbench:stats:badAlpha.
%
%   See also acousticbench.stats.pairedTTest, acousticbench.stats.wilcoxonTest.

arguments
    pValues double
    alpha (1,1) double = 0.05
end

if alpha <= 0 || alpha >= 1
    error('acousticbench:stats:badAlpha', 'Alpha must lie strictly between 0 and 1.');
end
if ~isvector(pValues)
    error('acousticbench:stats:badPValues', 'PVALUES must be a vector.');
end
pValues = pValues(:);
finiteMask = isfinite(pValues);
if any(pValues(finiteMask) < 0 | pValues(finiteMask) > 1)
    error('acousticbench:stats:badPValues', 'All p-values must lie in [0, 1].');
end

adjustedP = NaN(size(pValues));
rejected = false(size(pValues));
m = nnz(finiteMask);
if m == 0
    return;
end

finiteIndices = find(finiteMask);
[~, sortOrder] = sort(pValues(finiteIndices));
sortedIndices = finiteIndices(sortOrder);
sortedP = pValues(sortedIndices);

adjustedSorted = zeros(m, 1);
runningMaximum = 0;
for i = 1:m
    runningMaximum = max(runningMaximum, (m - i + 1) * sortedP(i));
    adjustedSorted(i) = min(1, runningMaximum);
end

adjustedP(sortedIndices) = adjustedSorted;
rejected(sortedIndices) = adjustedSorted <= alpha;
end
