classdef testGuiConstruction < matlab.unittest.TestCase
%TESTGUICONSTRUCTION Construction tests for the programmatic uifigure GUI.
%
%   The tests are skipped when no MATLAB desktop session is available
%   (usejava('desktop') is false), because uifigure construction is not
%   meaningful in that environment.  The GUI is created with 'Visible',
%   'off' and 'AutoLoad', false so no 90 MB MAT-file is loaded and no
%   window appears.
%
%   Run in MATLAB (with a desktop session):
%       addpath(genpath('matlab')); run_all_tests

    methods (TestClassSetup)
        function addPaths(testCase) %#ok<INUSD>
            here = fileparts(mfilename('fullpath'));
            matlabDir = fileparts(here);
            addpath(matlabDir);
            addpath(fullfile(matlabDir, 'gui'));
            addpath(fullfile(matlabDir, 'tests'));
            rehash;
        end
    end

    methods (Test)
        function testGuiConstructs(testCase)
            testCase.assumeTrue(usejava('desktop'), ...
                'GUI construction requires a MATLAB desktop session (usejava(''desktop'') is false).');
            testCase.assumeTrue(exist('uifigure', 'builtin') > 0 || exist('uifigure', 'file') > 0, ...
                'uifigure is not available in this MATLAB version.');
            app = AcousticBenchGUI('Visible', 'off', 'AutoLoad', false);
            testCase.addTeardown(@() safeCloseFigure(app.Figure));
            testCase.verifyTrue(isvalid(app.Figure));
            testCase.verifyTrue(isa(app.Figure, 'matlab.ui.Figure'));
            testCase.verifyEqual(app.Figure.Visible, 'off');
        end

        function testGuiHasSixTabs(testCase)
            testCase.assumeTrue(usejava('desktop'), ...
                'GUI construction requires a MATLAB desktop session.');
            app = AcousticBenchGUI('Visible', 'off', 'AutoLoad', false);
            testCase.addTeardown(@() safeCloseFigure(app.Figure));
            tabs = app.TabGroup.Children;
            testCase.verifyEqual(numel(tabs), 6);
            titles = cell(1, numel(tabs));
            for k = 1:numel(tabs)
                titles{k} = tabs(k).Title;
            end
            expected = {'Data Explorer', 'Frequency Response', 'Acoustic Feedback', ...
                'Repeatability', 'Hearing Threshold', 'Validation'};
            testCase.verifyEqual(titles, expected);
        end

        function testGuiHasCoreControls(testCase)
            testCase.assumeTrue(usejava('desktop'), ...
                'GUI construction requires a MATLAB desktop session.');
            app = AcousticBenchGUI('Visible', 'off', 'AutoLoad', false);
            testCase.addTeardown(@() safeCloseFigure(app.Figure));
            testCase.verifyTrue(isfield(app.UI, 'dataAxes'));
            testCase.verifyTrue(isfield(app.UI, 'frequencyAxes'));
            testCase.verifyTrue(isfield(app.UI, 'feedbackAxes'));
            testCase.verifyTrue(isfield(app.UI, 'repeatAxes'));
            testCase.verifyTrue(isfield(app.UI, 'thresholdAxes'));
            testCase.verifyTrue(isfield(app.UI, 'validationTable'));
            testCase.verifyTrue(isfield(app.UI, 'loadButton'));
            testCase.verifyTrue(isfield(app.UI, 'exportDataCsvButton'));
        end

        function testGuiValidationTabIsPopulated(testCase)
            testCase.assumeTrue(usejava('desktop'), ...
                'GUI construction requires a MATLAB desktop session.');
            app = AcousticBenchGUI('Visible', 'off', 'AutoLoad', false);
            testCase.addTeardown(@() safeCloseFigure(app.Figure));
            testCase.verifyEqual(size(app.UI.validationTable.Data, 1), 98);
        end
    end
end

% =======================================================================
function safeCloseFigure(figureHandle)
if ~isempty(figureHandle) && isvalid(figureHandle)
    close(figureHandle);
end
end
