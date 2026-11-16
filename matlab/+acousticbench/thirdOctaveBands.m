function bands = thirdOctaveBands(options)
%THIRDOCTAVEBANDS One-third-octave-band definitions.
%
%   BANDS = acousticbench.thirdOctaveBands() returns a 1xN struct array of
%   one-third-octave bands with the IEC 61260 nominal centre frequencies
%   from 25 Hz to 20 kHz, limited to the analysis range [20 Hz, 22050 Hz].
%
%   BANDS = acousticbench.thirdOctaveBands('Name', VALUE, ...)
%
%   Name-Value arguments
%       'FMin'     lower limit in Hz (default 20)
%       'FMax'     upper limit in Hz (default 22050)
%       'Centers'  explicit nominal centre frequencies
%
%   Band edges are centre/2^(1/6) and centre*2^(1/6), clipped to
%   [FMin, FMax]; bins are selected with lowHz <= f < highHz.
%
%   Fields: label, centerHz, lowHz, highHz
%
%   Example
%       bands = acousticbench.thirdOctaveBands('FMax', 8000);
%
%   See also acousticbench.octaveBands, acousticbench.bandLevels.

arguments
    options.FMin (1,1) double {mustBePositive} = 20
    options.FMax (1,1) double {mustBePositive} = 22050
    options.Centers double = []
end

if isempty(options.Centers)
    centres = [25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, ...
               400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, ...
               4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000];
else
    centres = options.Centers(:)';
end
ratio = 2 ^ (1 / 6);
bands = buildBands(centres, ratio, options.FMin, options.FMax);
end

% =======================================================================
function bands = buildBands(centres, ratio, fMin, fMax)
template = struct('label', '', 'centerHz', 0, 'lowHz', 0, 'highHz', 0);
bands = repmat(template, 1, 0);
for k = 1:numel(centres)
    centre = centres(k);
    low = max(centre / ratio, fMin);
    high = min(centre * ratio, fMax);
    if low >= high
        continue;
    end
    band = template;
    band.label = sprintf('%g Hz', centre);
    band.centerHz = centre;
    band.lowHz = low;
    band.highHz = high;
    bands(end + 1) = band; %#ok<AGROW>
end
end
