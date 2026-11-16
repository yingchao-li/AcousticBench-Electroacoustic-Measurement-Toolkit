function [dz, standardError] = cohensDz(x, y)
%COHENSDZ Cohen's dz effect size for paired samples.
%
%   DZ = acousticbench.stats.cohensDz(X, Y) returns Cohen's dz, the mean of
%   the paired differences divided by their standard deviation:
%
%       dz = mean(X - Y) / std(X - Y, 0)
%
%   where std(..., 0) is the sample standard deviation (n-1 denominator).
%   The subject is the statistical unit: pass one value per subject
%   (reinsertions averaged beforehand if applicable) and a zero vector as Y
%   to obtain the one-sample effect size of the differences.
%
%   [DZ, SE] = ... also returns the large-sample standard error
%       SE = sqrt((1 + dz^2 / 2) / n)
%   which can be used for an approximate normal CI.
%
%   Example
%       d = [1 2 3 4 5];
%       dz = acousticbench.stats.cohensDz(d, zeros(size(d)));   % 3.0
%
%   Error identifiers: acousticbench:stats:badData.

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
if numel(x) < 2
    error('acousticbench:stats:badData', ...
        'Cohen''s dz requires at least two pairs.');
end
differences = x - y;
sd = std(differences, 0);
if sd == 0
    dz = NaN;
    standardError = NaN;
    return;
end
dz = mean(differences) / sd;
standardError = sqrt((1 + dz ^ 2 / 2) / numel(differences));
end
