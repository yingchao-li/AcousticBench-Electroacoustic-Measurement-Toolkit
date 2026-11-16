function results = run_all_tests(outputDirectory)
%RUN_ALL_TESTS Run the complete MATLAB unittest suite of AcousticBench.
%
%   RESULTS = run_all_tests() discovers all matlab.unittest.TestCase
%   classes in matlab/tests and runs them with text output.  The script
%   adds the required folders to the MATLAB path first, so it can be started
%   from any working directory (provided this file is found):
%
%       addpath('matlab'); run_all_tests
%   or, with the matlab folder on the path:
%       matlab -batch "run_all_tests"
%
%   RESULTS = run_all_tests(OUTPUTDIRECTORY) additionally writes a plain
%   text log to OUTPUTDIRECTORY/acousticbench_matlab_tests.txt.
%
%   The function raises an error (acousticbench:tests:failed) when at least
%   one test fails, so `matlab -batch` exits with a non-zero status.  The
%   summary line reports passed/failed/incomplete counts and the total
%   duration.
%
%   Example
%       results = run_all_tests();
%       nnz([results.Failed])
%
%   See also matlab.unittest.TestSuite, matlab.unittest.TestRunner.

arguments
    outputDirectory {mustBeTextScalar} = ''
end

thisFile = mfilename('fullpath');
testsDirectory = fileparts(thisFile);
matlabDirectory = fileparts(testsDirectory);
repoRoot = fileparts(matlabDirectory);
addpath(matlabDirectory);
addpath(fullfile(matlabDirectory, 'gui'));
addpath(testsDirectory);
rehash;

import matlab.unittest.TestSuite
import matlab.unittest.TestRunner

fprintf('AcousticBench MATLAB test suite\n');
fprintf('  repository root : %s\n', repoRoot);
fprintf('  MATLAB version  : %s\n', version);
fprintf('  tests directory : %s\n\n', testsDirectory);

suite = TestSuite.fromFolder(testsDirectory);
runner = TestRunner.withTextOutput('Verbosity', 2);
results = runner.run(suite);

nTotal = numel(results);
nFailed = nnz([results.Failed]);
nIncomplete = nnz([results.Incomplete]);
nPassed = nTotal - nFailed - nIncomplete;
totalDuration = sum([results.Duration]);

fprintf('\nSummary: %d passed, %d failed, %d incomplete (%.2f s)\n', ...
    nPassed, nFailed, nIncomplete, totalDuration);
for k = 1:nTotal
    if results(k).Failed
        fprintf('  FAILED: %s\n', results(k).Name);
    elseif results(k).Incomplete
        fprintf('  INCOMPLETE (assumption failed): %s\n', results(k).Name);
    end
end

if strlength(string(outputDirectory)) > 0
    logDirectory = char(outputDirectory);
    if ~isfolder(logDirectory)
        mkdir(logDirectory);
    end
    logPath = fullfile(logDirectory, 'acousticbench_matlab_tests.txt');
    fid = fopen(logPath, 'w');
    if fid >= 0
        fprintf(fid, 'AcousticBench MATLAB test log\n');
        fprintf(fid, 'MATLAB version: %s\n', version);
        fprintf(fid, 'Tests directory: %s\n\n', testsDirectory);
        for k = 1:nTotal
            fprintf(fid, '%-6s %-60s %.3f s\n', ...
                passStatus(results(k)), results(k).Name, results(k).Duration);
        end
        fprintf(fid, '\nSummary: %d passed, %d failed, %d incomplete (%.2f s)\n', ...
            nPassed, nFailed, nIncomplete, totalDuration);
        fclose(fid);
        fprintf('Test log written to %s\n', logPath);
    end
end

if nFailed > 0
    error('acousticbench:tests:failed', '%d test(s) failed.', nFailed);
end
end

% =======================================================================
function status = passStatus(result)
if result.Failed
    status = 'FAIL';
elseif result.Incomplete
    status = 'SKIP';
else
    status = 'PASS';
end
end
