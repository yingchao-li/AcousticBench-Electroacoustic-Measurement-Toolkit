function c = constants()
%CONSTANTS Physical and dataset constants for the AcousticBench dataset.
%
%   C = acousticbench.constants() returns a scalar struct with the
%   constants documented for the Denk, Hackenberg & Husstedt (2026)
%   dataset (doi:10.5281/zenodo.20023285) and used throughout the MATLAB
%   toolkit.  Keeping them in one place avoids magic numbers in the
%   analysis and validation code.
%
%   Fields
%       pRefPa                 reference sound pressure 20e-6 Pa (0 dB SPL)
%       uHaDriveV              hearing-aid receiver drive voltage 11.2e-3 V
%       dbSplOffset            20*log10(1/pRefPa) ~ 93.9794 dB
%       nyquistHz              22050 Hz (DFT grid upper edge)
%       nFrequencies           2049 transfer-function bins (including DC)
%       nThresholdFrequencies  6 audiometric frequencies
%       nSubjects              14
%       nReinsertions          3
%       nDevices               14 (7 earpiece families x ref/meas)
%       nFamilies              7
%       frequencyResolutionHz  22050/2048 = 10.7666015625 Hz
%       defaultSeed            20260422 (synthetic cases, bootstrap)
%
%   Example
%       c = acousticbench.constants();
%       fprintf('0 dB SPL = %.4f dB re 1 Pa\n', c.dbSplOffset);
%
%   See also acousticbench.deviceTable.

c = struct( ...
    'pRefPa', 20e-6, ...
    'uHaDriveV', 11.2e-3, ...
    'dbSplOffset', 20 * log10(1 / 20e-6), ...
    'nyquistHz', 22050, ...
    'nFrequencies', 2049, ...
    'nThresholdFrequencies', 6, ...
    'nSubjects', 14, ...
    'nReinsertions', 3, ...
    'nDevices', 14, ...
    'nFamilies', 7, ...
    'frequencyResolutionHz', 22050 / 2048, ...
    'defaultSeed', 20260422);
end
