function bands = octaveBands(options)
%OCTAVEBANDS Octave-band definitions (IEC 61260 nominal centres).
%
%   BANDS = acousticbench.octaveBands() returns a 1xN struct array of
%   octave bands with nominal centre frequencies 31.5 Hz .. 16 kHz,
%   limited to the analysis range [20 Hz, 22050 Hz].
%
%   BANDS = acousticbench.octaveBands('Name', VALUE, ...)
%
%   Name-Value arguments
%       'FMin'     lower limit in Hz (default 20)
%       'FMax'     upper limit in Hz (default 22050)
%       'Centers'  explicit nominal centre frequencies (default the
%                  standard octave series)
%
%   Band edges are centre/sqrt(2) and centre*sqrt(2), clipped to
%   [FMin, FMax]; a band whose edges collapse is dropped.  Bins are
%   selected with lowHz <= f < highHz (standard power-average convention).
%
%   Fields: label, centerHz, lowHz, highHz
%
%   Example
%       bands = acousticbench.octaveBands('Centers', [500 1000 2000 4000]);
%       disp([ [bands.centerHz]' [bands.lowHz]' [bands.highHz]' ])
%
%   See also acousticbench.thirdOctaveBands, acousticbench.bandLevels.

arguments
    options.FMin (1,1) double {mustBePositive} = 20
    options.FMax (1,1) double {mustBePositive} = 22050
    options.Centers double = []
end

if isempty(options.Centers)
    centres = [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];
else
    centres = options.Centers(:)';
end
bands = buildBands(centres, sqrt(2), options.FMin, options.FMax);
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
