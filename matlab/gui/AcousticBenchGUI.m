function app = AcousticBenchGUI(varargin)
%ACOUSTICBENCHGUI Programmatic AcousticBench desktop application (uifigure).
%
%   APP = AcousticBenchGUI() opens the AcousticBench MATLAB application in
%   a programmatic uifigure (no .mlapp file is used; the whole UI is built
%   from code, so it is reviewable and diff-able).  Data.mat is loaded
%   automatically from the repository root when present.
%
%   APP = AcousticBenchGUI('Name', VALUE, ...)
%
%   Name-Value arguments
%       'DataPath'  default '' -> <repo>/Data.mat
%       'Visible'   'on' (default) or 'off' (for automated construction tests)
%       'AutoLoad'  load Data.mat on startup (default true)
%
%   Output APP (struct)
%       Figure    the uifigure handle
%       TabGroup  uitabgroup handle
%       UI        struct of the main UI handles
%
%   Tabs and contents
%       Data Explorer        container, condition, subset and statistic
%                            selectors; median/mean transfer-function levels
%                            per device code; PNG/CSV export.
%       Frequency Response   family and metric selectors; Hha (reference
%                            probe / measurement probe) or feedback path
%                            median curves; PNG/CSV export.
%       Acoustic Feedback    feedback path |M_ha2haf| per device; median
%                            level curve; PNG/CSV export.
%       Repeatability        within-subject reinsertion standard deviation
%                            of Hha (median and 95th percentile); PNG/CSV.
%       Hearing Threshold    median threshold [dBV] versus audiometric
%                            frequency, reference vs measurement condition;
%                            PNG/CSV export.
%       Validation           structural validity table and NaN-session
%                            summary; CSV export.
%
%   The GUI is a viewer only: it masks measured NaNs and structurally
%   invalid values exactly like the analysis functions and never imputes.
%
%   Example
%       addpath(genpath('matlab'));
%       app = AcousticBenchGUI();
%       % or, headless construction for automated checks:
%       app = AcousticBenchGUI('Visible', 'off', 'AutoLoad', false);
%
%   See also acousticbench.loadData, acousticbench.hha,
%   acousticbench.reoig, acousticbench.feedbackPath,
%   acousticbench.thresholdTable, acousticbench.structuralValidityTable.

options = struct('DataPath', '', 'Visible', 'on', 'AutoLoad', true);
if mod(numel(varargin), 2) ~= 0
    error('acousticbench:gui:badArguments', ...
        'Name-value arguments must be given in pairs.');
end
for k = 1:2:numel(varargin)
    argumentName = lower(char(varargin{k}));
    argumentValue = varargin{k + 1};
    switch argumentName
        case 'datapath'
            options.DataPath = char(argumentValue);
        case 'visible'
            options.Visible = char(argumentValue);
        case 'autoload'
            options.AutoLoad = logical(argumentValue);
        otherwise
            error('acousticbench:gui:unknownArgument', ...
                'Unknown argument "%s"; expected DataPath, Visible or AutoLoad.', ...
                char(varargin{k}));
    end
end

thisFile = mfilename('fullpath');
guiDir = fileparts(thisFile);
matlabDir = fileparts(guiDir);
repoRoot = fileparts(matlabDir);
addpath(genpath(matlabDir));
rehash;

visible = validatestring(char(options.Visible), {'on', 'off'}, mfilename, 'Visible');
if ~isscalar(options.AutoLoad)
    error('acousticbench:gui:badArguments', 'AutoLoad must be a logical scalar.');
end
devices = acousticbench.deviceTable();

state = struct();
state.data = [];
state.dataPath = '';
state.plottedTable = [];
state.plottedName = 'acousticbench_export';

ui = struct();
ui.repoRoot = repoRoot;
ui.devices = devices;

app.Figure = uifigure( ...
    'Name', 'AcousticBench - MATLAB GUI', ...
    'Position', [60 60 1300 840], ...
    'Visible', visible);
fig = app.Figure;

mainGrid = uigridlayout(fig, [2, 1]);
mainGrid.RowHeight = {'1x', 30};
mainGrid.Padding = [8 8 8 8];
mainGrid.RowSpacing = 6;

ui.tabGroup = uitabgroup(mainGrid);
ui.tabGroup.Layout.Row = 1;
tabGroup = ui.tabGroup;

ui.statusLabel = uilabel(mainGrid, 'Text', 'Ready. Load Data.mat to begin.');
ui.statusLabel.Layout.Row = 2;
ui.statusLabel.FontAngle = 'italic';

tabData = uitab(tabGroup, 'Title', 'Data Explorer');
tabFrequency = uitab(tabGroup, 'Title', 'Frequency Response');
tabFeedback = uitab(tabGroup, 'Title', 'Acoustic Feedback');
tabRepeat = uitab(tabGroup, 'Title', 'Repeatability');
tabThreshold = uitab(tabGroup, 'Title', 'Hearing Threshold');
tabValidation = uitab(tabGroup, 'Title', 'Validation');

%% Data Explorer tab ----------------------------------------------------
ui.dataGrid = uigridlayout(tabData, [1, 2]);
ui.dataGrid.ColumnWidth = {320, '1x'};
dataControls = uipanel(ui.dataGrid, 'Title', 'Selection');
dataControls.Layout.Row = 1;
dataControls.Layout.Column = 1;
dataLayout = uigridlayout(dataControls, [11, 2]);
dataLayout.RowHeight = repmat({26}, 1, 11);
dataLayout.ColumnWidth = {110, '1x'};
dataLayout.RowSpacing = 4;

ui.loadButton = uibutton(dataLayout, 'Text', 'Load Data.mat ...', ...
    'ButtonPushedFcn', @(~, ~) onLoadButton());
ui.loadButton.Layout.Row = 1;
ui.loadButton.Layout.Column = [1 2];

ui.dataPathLabel = uilabel(dataLayout, 'Text', '(no data loaded)');
ui.dataPathLabel.Layout.Row = 2;
ui.dataPathLabel.Layout.Column = [1 2];

addGridLabel(dataLayout, 'Container', 3);
ui.containerDropdown = uidropdown(dataLayout, ...
    'Items', {'M_ha2edR (earmold RPT)', 'M_ha2edM (probe tube)', 'M_ha2haf (feedback)'}, ...
    'Value', 'M_ha2edR (earmold RPT)');
ui.containerDropdown.Layout.Row = 3;
ui.containerDropdown.Layout.Column = 2;

addGridLabel(dataLayout, 'Condition', 4);
ui.conditionDropdown = uidropdown(dataLayout, ...
    'Items', {'all', 'reference', 'measurement'}, 'Value', 'measurement');
ui.conditionDropdown.Layout.Row = 4;
ui.conditionDropdown.Layout.Column = 2;

addGridLabel(dataLayout, 'Subset', 5);
ui.subsetDropdown = uidropdown(dataLayout, ...
    'Items', {'all', 'earmolds', 'domes'}, 'Value', 'earmolds');
ui.subsetDropdown.Layout.Row = 5;
ui.subsetDropdown.Layout.Column = 2;

addGridLabel(dataLayout, 'Statistic', 6);
ui.statisticDropdown = uidropdown(dataLayout, ...
    'Items', {'median', 'mean'}, 'Value', 'median');
ui.statisticDropdown.Layout.Row = 6;
ui.statisticDropdown.Layout.Column = 2;

ui.plotDataButton = uibutton(dataLayout, 'Text', 'Plot levels', ...
    'ButtonPushedFcn', @(~, ~) onPlotExplorer());
ui.plotDataButton.Layout.Row = 7;
ui.plotDataButton.Layout.Column = [1 2];

ui.exportDataPngButton = uibutton(dataLayout, 'Text', 'Export PNG ...', ...
    'ButtonPushedFcn', @(~, ~) onExportPng());
ui.exportDataPngButton.Layout.Row = 8;
ui.exportDataPngButton.Layout.Column = 1;
ui.exportDataCsvButton = uibutton(dataLayout, 'Text', 'Export CSV ...', ...
    'ButtonPushedFcn', @(~, ~) onExportCsv());
ui.exportDataCsvButton.Layout.Row = 8;
ui.exportDataCsvButton.Layout.Column = 2;

ui.dataInfoLabel = uilabel(dataLayout, 'Text', '');
ui.dataInfoLabel.Layout.Row = 9;
ui.dataInfoLabel.Layout.Column = [1 2];
ui.dataInfoLabel.WordWrap = 'on';

ui.dataAxes = uiaxes(ui.dataGrid);
ui.dataAxes.Layout.Row = 1;
ui.dataAxes.Layout.Column = 2;
configureAxes(ui.dataAxes, 'Frequency [Hz]', 'Level [dB]', 'Data Explorer');

%% Frequency Response tab ----------------------------------------------
ui.frequencyGrid = uigridlayout(tabFrequency, [1, 2]);
ui.frequencyGrid.ColumnWidth = {320, '1x'};
frequencyControls = uipanel(ui.frequencyGrid, 'Title', 'Selection');
frequencyControls.Layout.Row = 1;
frequencyControls.Layout.Column = 1;
frequencyLayout = uigridlayout(frequencyControls, [8, 2]);
frequencyLayout.RowHeight = repmat({26}, 1, 8);
frequencyLayout.ColumnWidth = {110, '1x'};
frequencyLayout.RowSpacing = 4;

addGridLabel(frequencyLayout, 'Family', 1);
ui.familyDropdown = uidropdown(frequencyLayout, ...
    'Items', familyLabels(devices), 'Value', familyLabels(devices){1});
ui.familyDropdown.Layout.Row = 1;
ui.familyDropdown.Layout.Column = 2;

addGridLabel(frequencyLayout, 'Metric', 2);
ui.frequencyMetricDropdown = uidropdown(frequencyLayout, ...
    'Items', {'Hha (M_ha2edR)', 'Hha (M_ha2edM)', 'Feedback path (M_ha2haf)'}, ...
    'Value', 'Hha (M_ha2edR)');
ui.frequencyMetricDropdown.Layout.Row = 2;
ui.frequencyMetricDropdown.Layout.Column = 2;

addGridLabel(frequencyLayout, 'Condition', 3);
ui.frequencyConditionDropdown = uidropdown(frequencyLayout, ...
    'Items', {'reference', 'measurement', 'all'}, 'Value', 'measurement');
ui.frequencyConditionDropdown.Layout.Row = 3;
ui.frequencyConditionDropdown.Layout.Column = 2;

ui.plotFrequencyButton = uibutton(frequencyLayout, 'Text', 'Plot response', ...
    'ButtonPushedFcn', @(~, ~) onPlotFrequencyResponse());
ui.plotFrequencyButton.Layout.Row = 4;
ui.plotFrequencyButton.Layout.Column = [1 2];

ui.exportFrequencyPngButton = uibutton(frequencyLayout, 'Text', 'Export PNG ...', ...
    'ButtonPushedFcn', @(~, ~) onExportPng());
ui.exportFrequencyPngButton.Layout.Row = 5;
ui.exportFrequencyPngButton.Layout.Column = 1;
ui.exportFrequencyCsvButton = uibutton(frequencyLayout, 'Text', 'Export CSV ...', ...
    'ButtonPushedFcn', @(~, ~) onExportCsv());
ui.exportFrequencyCsvButton.Layout.Row = 5;
ui.exportFrequencyCsvButton.Layout.Column = 2;

ui.frequencyInfoLabel = uilabel(frequencyLayout, 'Text', '');
ui.frequencyInfoLabel.Layout.Row = 6;
ui.frequencyInfoLabel.Layout.Column = [1 2];
ui.frequencyInfoLabel.WordWrap = 'on';

ui.frequencyAxes = uiaxes(ui.frequencyGrid);
ui.frequencyAxes.Layout.Row = 1;
ui.frequencyAxes.Layout.Column = 2;
configureAxes(ui.frequencyAxes, 'Frequency [Hz]', 'Level [dB]', 'Frequency Response');

%% Acoustic Feedback tab ------------------------------------------------
ui.feedbackGrid = uigridlayout(tabFeedback, [1, 2]);
ui.feedbackGrid.ColumnWidth = {320, '1x'};
feedbackControls = uipanel(ui.feedbackGrid, 'Title', 'Selection');
feedbackControls.Layout.Row = 1;
feedbackControls.Layout.Column = 1;
feedbackLayout = uigridlayout(feedbackControls, [7, 2]);
feedbackLayout.RowHeight = repmat({26}, 1, 7);
feedbackLayout.ColumnWidth = {110, '1x'};
feedbackLayout.RowSpacing = 4;

addGridLabel(feedbackLayout, 'Device', 1);
ui.feedbackDeviceDropdown = uidropdown(feedbackLayout, ...
    'Items', deviceLabels(devices), 'Value', deviceLabels(devices){2});
ui.feedbackDeviceDropdown.Layout.Row = 1;
ui.feedbackDeviceDropdown.Layout.Column = 2;

addGridLabel(feedbackLayout, 'Condition', 2);
ui.feedbackConditionDropdown = uidropdown(feedbackLayout, ...
    'Items', {'measurement', 'reference', 'all'}, 'Value', 'measurement');
ui.feedbackConditionDropdown.Layout.Row = 2;
ui.feedbackConditionDropdown.Layout.Column = 2;

ui.plotFeedbackButton = uibutton(feedbackLayout, 'Text', 'Plot feedback path', ...
    'ButtonPushedFcn', @(~, ~) onPlotFeedback());
ui.plotFeedbackButton.Layout.Row = 3;
ui.plotFeedbackButton.Layout.Column = [1 2];

ui.exportFeedbackPngButton = uibutton(feedbackLayout, 'Text', 'Export PNG ...', ...
    'ButtonPushedFcn', @(~, ~) onExportPng());
ui.exportFeedbackPngButton.Layout.Row = 4;
ui.exportFeedbackPngButton.Layout.Column = 1;
ui.exportFeedbackCsvButton = uibutton(feedbackLayout, 'Text', 'Export CSV ...', ...
    'ButtonPushedFcn', @(~, ~) onExportCsv());
ui.exportFeedbackCsvButton.Layout.Row = 4;
ui.exportFeedbackCsvButton.Layout.Column = 2;

ui.feedbackInfoLabel = uilabel(feedbackLayout, 'Text', '');
ui.feedbackInfoLabel.Layout.Row = 5;
ui.feedbackInfoLabel.Layout.Column = [1 2];
ui.feedbackInfoLabel.WordWrap = 'on';

ui.feedbackAxes = uiaxes(ui.feedbackGrid);
ui.feedbackAxes.Layout.Row = 1;
ui.feedbackAxes.Layout.Column = 2;
configureAxes(ui.feedbackAxes, 'Frequency [Hz]', 'Feedback path level [dB SPL]', 'Acoustic Feedback');

%% Repeatability tab ----------------------------------------------------
ui.repeatGrid = uigridlayout(tabRepeat, [1, 2]);
ui.repeatGrid.ColumnWidth = {320, '1x'};
repeatControls = uipanel(ui.repeatGrid, 'Title', 'Selection');
repeatControls.Layout.Row = 1;
repeatControls.Layout.Column = 1;
repeatLayout = uigridlayout(repeatControls, [6, 2]);
repeatLayout.RowHeight = repmat({26}, 1, 6);
repeatLayout.ColumnWidth = {110, '1x'};
repeatLayout.RowSpacing = 4;

addGridLabel(repeatLayout, 'Container', 1);
ui.repeatContainerDropdown = uidropdown(repeatLayout, ...
    'Items', {'M_ha2edR', 'M_ha2edM'}, 'Value', 'M_ha2edR');
ui.repeatContainerDropdown.Layout.Row = 1;
ui.repeatContainerDropdown.Layout.Column = 2;

addGridLabel(repeatLayout, 'Condition', 2);
ui.repeatConditionDropdown = uidropdown(repeatLayout, ...
    'Items', {'measurement', 'reference', 'all'}, 'Value', 'measurement');
ui.repeatConditionDropdown.Layout.Row = 2;
ui.repeatConditionDropdown.Layout.Column = 2;

ui.plotRepeatButton = uibutton(repeatLayout, 'Text', 'Plot reinsertion SD', ...
    'ButtonPushedFcn', @(~, ~) onPlotRepeatability());
ui.plotRepeatButton.Layout.Row = 3;
ui.plotRepeatButton.Layout.Column = [1 2];

ui.exportRepeatPngButton = uibutton(repeatLayout, 'Text', 'Export PNG ...', ...
    'ButtonPushedFcn', @(~, ~) onExportPng());
ui.exportRepeatPngButton.Layout.Row = 4;
ui.exportRepeatPngButton.Layout.Column = 1;
ui.exportRepeatCsvButton = uibutton(repeatLayout, 'Text', 'Export CSV ...', ...
    'ButtonPushedFcn', @(~, ~) onExportCsv());
ui.exportRepeatCsvButton.Layout.Row = 4;
ui.exportRepeatCsvButton.Layout.Column = 2;

ui.repeatInfoLabel = uilabel(repeatLayout, 'Text', '');
ui.repeatInfoLabel.Layout.Row = 5;
ui.repeatInfoLabel.Layout.Column = [1 2];
ui.repeatInfoLabel.WordWrap = 'on';

ui.repeatAxes = uiaxes(ui.repeatGrid);
ui.repeatAxes.Layout.Row = 1;
ui.repeatAxes.Layout.Column = 2;
configureAxes(ui.repeatAxes, 'Frequency [Hz]', 'Reinsertion SD [dB]', 'Repeatability');

%% Hearing Threshold tab ------------------------------------------------
ui.thresholdGrid = uigridlayout(tabThreshold, [1, 2]);
ui.thresholdGrid.ColumnWidth = {320, '1x'};
thresholdControls = uipanel(ui.thresholdGrid, 'Title', 'Selection');
thresholdControls.Layout.Row = 1;
thresholdControls.Layout.Column = 1;
thresholdLayout = uigridlayout(thresholdControls, [6, 2]);
thresholdLayout.RowHeight = repmat({26}, 1, 6);
thresholdLayout.ColumnWidth = {110, '1x'};
thresholdLayout.RowSpacing = 4;

addGridLabel(thresholdLayout, 'Family', 1);
ui.thresholdFamilyDropdown = uidropdown(thresholdLayout, ...
    'Items', familyLabels(devices), 'Value', familyLabels(devices){1});
ui.thresholdFamilyDropdown.Layout.Row = 1;
ui.thresholdFamilyDropdown.Layout.Column = 2;

addGridLabel(thresholdLayout, 'Statistic', 2);
ui.thresholdStatisticDropdown = uidropdown(thresholdLayout, ...
    'Items', {'median', 'mean'}, 'Value', 'median');
ui.thresholdStatisticDropdown.Layout.Row = 2;
ui.thresholdStatisticDropdown.Layout.Column = 2;

ui.plotThresholdButton = uibutton(thresholdLayout, 'Text', 'Plot thresholds', ...
    'ButtonPushedFcn', @(~, ~) onPlotThreshold());
ui.plotThresholdButton.Layout.Row = 3;
ui.plotThresholdButton.Layout.Column = [1 2];

ui.exportThresholdPngButton = uibutton(thresholdLayout, 'Text', 'Export PNG ...', ...
    'ButtonPushedFcn', @(~, ~) onExportPng());
ui.exportThresholdPngButton.Layout.Row = 4;
ui.exportThresholdPngButton.Layout.Column = 1;
ui.exportThresholdCsvButton = uibutton(thresholdLayout, 'Text', 'Export CSV ...', ...
    'ButtonPushedFcn', @(~, ~) onExportCsv());
ui.exportThresholdCsvButton.Layout.Row = 4;
ui.exportThresholdCsvButton.Layout.Column = 2;

ui.thresholdInfoLabel = uilabel(thresholdLayout, 'Text', '');
ui.thresholdInfoLabel.Layout.Row = 5;
ui.thresholdInfoLabel.Layout.Column = [1 2];
ui.thresholdInfoLabel.WordWrap = 'on';

ui.thresholdAxes = uiaxes(ui.thresholdGrid);
ui.thresholdAxes.Layout.Row = 1;
ui.thresholdAxes.Layout.Column = 2;
configureAxes(ui.thresholdAxes, 'Frequency [Hz]', 'Threshold [dBV]', 'Hearing Threshold');

%% Validation tab -------------------------------------------------------
ui.validationGrid = uigridlayout(tabValidation, [2, 1]);
ui.validationGrid.RowHeight = {'1x', 130};
ui.validationTable = uitable(ui.validationGrid);
ui.validationTable.Layout.Row = 1;
ui.validationTable.ColumnName = {'Container', 'Code', 'Family', 'Coupling', ...
    'Condition', 'StructurallyValid', 'Rationale'};
ui.validationTable.ColumnWidth = {100, 50, 150, 80, 100, 130, 500};
ui.validationSummary = uitextarea(ui.validationGrid, 'Editable', 'off');
ui.validationSummary.Layout.Row = 2;
ui.validationSummary.Value = {'Load Data.mat to populate the validation summary.'};

app.TabGroup = tabGroup;
app.UI = ui;

%% Startup --------------------------------------------------------------
refreshValidationTab();
if options.AutoLoad
    if strlength(string(options.DataPath)) > 0
        loadDataFromPath(char(options.DataPath));
    else
        loadDataFromPath(fullfile(repoRoot, 'Data.mat'));
    end
end

%% ===================== nested functions ==============================
    function loadDataFromPath(path)
        if exist(path, 'file') ~= 2
            setStatus(sprintf('Data file not found: %s', path));
            return;
        end
        try
            data = acousticbench.loadData(path);
        catch err
            setStatus(sprintf('Load failed: %s', err.message));
            return;
        end
        state.data = data;
        state.dataPath = path;
        ui.dataPathLabel.Text = sprintf('Loaded: %s', data.fileName);
        setStatus(sprintf('Loaded %s: %d devices x %d subjects x %d reinsertions', ...
            data.fileName, numel(data.devices), numel(data.subjects), numel(data.reinsertions)));
        refreshValidationTab();
    end

    function onLoadButton()
        [fileName, folder] = uigetfile({'*.mat', 'MAT-files (*.mat)'}, ...
            'Select the AcousticBench Data.mat file', ui.repoRoot);
        if isequal(fileName, 0)
            return;
        end
        loadDataFromPath(fullfile(folder, fileName));
    end

    function onPlotExplorer()
        if ~ensureData()
            return;
        end
        containerLabels = {'M_ha2edR (earmold RPT)', 'M_ha2edM (probe tube)', 'M_ha2haf (feedback)'};
        containers = {'M_ha2edR', 'M_ha2edM', 'M_ha2haf'};
        container = containers{strcmp(containerLabels, ui.containerDropdown.Value)};
        condition = ui.conditionDropdown.Value;
        deviceCodes = selectedDeviceCodes();
        try
            if strcmp(container, 'M_ha2haf')
                [levels, ~, info] = acousticbench.feedbackPath(state.data, ...
                    'Condition', condition, 'DeviceCodes', deviceCodes);
            else
                [levels, ~, info] = acousticbench.hha(state.data, ...
                    'Container', container, 'Condition', condition, ...
                    'DeviceCodes', deviceCodes);
            end
        catch err
            setStatus(sprintf('Plot failed: %s', err.message));
            return;
        end
        statistic = ui.statisticDropdown.Value;
        deviceCodes = info.deviceCodes;
        if strcmp(statistic, 'median')
            summary = nanmedian(nanmedian(levels, 3), 4);
        else
            summary = nanmean(nanmean(levels, 3), 4);
        end
        summary = reshape(summary, size(levels, 1), numel(deviceCodes));
        freq = state.data.frequency;
        cla(ui.dataAxes);
        labels = cell(1, size(summary, 2));
        hold(ui.dataAxes, 'on');
        for column = 1:size(summary, 2)
            semilogx(ui.dataAxes, freq, summary(:, column));
            labels{column} = deviceLabelForCode(info.deviceCodes(column));
        end
        hold(ui.dataAxes, 'off');
        legend(ui.dataAxes, labels, 'Location', 'southwest');
        configureAxes(ui.dataAxes, 'Frequency [Hz]', 'Level [dB]', ...
            sprintf('%s - %s (%s)', container, condition, statistic));
        state.plottedName = sprintf('acousticbench_%s_%s', container, condition);
        state.plottedTable = [table(freq, 'VariableNames', {'FrequencyHz'}), ...
            array2table(summary, 'VariableNames', makeValidNames(labels))];
        ui.dataInfoLabel.Text = sprintf('%d device curves, %d frequency bins', ...
            size(summary, 2), numel(freq));
        setStatus(sprintf('Plotted %s levels (%s).', container, statistic));
    end

    function onPlotFrequencyResponse()
        if ~ensureData()
            return;
        end
        familyIndex = find(strcmp(familyLabels(ui.devices), ui.familyDropdown.Value), 1);
        family = ui.devices(2 * familyIndex - 1).family;
        familyCodes = [ui.devices(strcmp({ui.devices.family}, family)).code];
        metric = ui.frequencyMetricDropdown.Value;
        condition = ui.frequencyConditionDropdown.Value;
        try
            if strcmp(metric, 'Feedback path (M_ha2haf)')
                [levels, ~, info] = acousticbench.feedbackPath(state.data, ...
                    'Condition', condition, 'DeviceCodes', familyCodes);
                yText = 'Feedback path [dB SPL]';
            elseif strcmp(metric, 'Hha (M_ha2edM)')
                [levels, ~, info] = acousticbench.hha(state.data, 'Container', 'M_ha2edM', ...
                    'Condition', condition, 'DeviceCodes', familyCodes);
                yText = 'Hha [dB SPL]';
            else
                [levels, ~, info] = acousticbench.hha(state.data, 'Container', 'M_ha2edR', ...
                    'Condition', condition, 'DeviceCodes', familyCodes);
                yText = 'Hha [dB SPL]';
            end
        catch err
            setStatus(sprintf('Plot failed: %s', err.message));
            return;
        end
        summary = reshape(nanmedian(nanmedian(levels, 3), 4), ...
            size(levels, 1), numel(info.deviceCodes));
        freq = state.data.frequency;
        cla(ui.frequencyAxes);
        hold(ui.frequencyAxes, 'on');
        labels = cell(1, size(summary, 2));
        for column = 1:size(summary, 2)
            semilogx(ui.frequencyAxes, freq, summary(:, column));
            labels{column} = deviceLabelForCode(info.deviceCodes(column));
        end
        hold(ui.frequencyAxes, 'off');
        legend(ui.frequencyAxes, labels, 'Location', 'southwest');
        configureAxes(ui.frequencyAxes, 'Frequency [Hz]', yText, ...
            sprintf('%s - %s', ui.familyDropdown.Value, ui.frequencyConditionDropdown.Value));
        state.plottedName = sprintf('acousticbench_frequency_%s', family);
        state.plottedTable = [table(freq, 'VariableNames', {'FrequencyHz'}), ...
            array2table(summary, 'VariableNames', makeValidNames(labels))];
        ui.frequencyInfoLabel.Text = sprintf('Family %s, codes %s', ...
            family, mat2str(familyCodes));
        setStatus('Plotted frequency response.');
    end

    function onPlotFeedback()
        if ~ensureData()
            return;
        end
        labelIndex = find(strcmp(deviceLabels(ui.devices), ui.feedbackDeviceDropdown.Value), 1);
        code = ui.devices(labelIndex).code;
        try
            [levels, ~, info] = acousticbench.feedbackPath(state.data, ...
                'Condition', ui.feedbackConditionDropdown.Value, ...
                'DeviceCodes', code);
        catch err
            setStatus(sprintf('Plot failed: %s', err.message));
            return;
        end
        summary = reshape(nanmedian(nanmedian(levels, 3), 4), size(levels, 1), 1);
        freq = state.data.frequency;
        cla(ui.feedbackAxes);
        semilogx(ui.feedbackAxes, freq, summary);
        configureAxes(ui.feedbackAxes, 'Frequency [Hz]', 'Feedback path level [dB SPL]', ...
            sprintf('%s - %s', ui.feedbackDeviceDropdown.Value, ...
            ui.feedbackConditionDropdown.Value));
        ui.feedbackInfoLabel.Text = sprintf('Device code %d, %d bins', code, numel(freq));
        state.plottedName = sprintf('acousticbench_feedback_code%02d', code);
        state.plottedTable = table(freq, summary, ...
            'VariableNames', {'FrequencyHz', 'FeedbackPathLevelDbSpl'});
        setStatus('Plotted feedback path.');
    end

    function onPlotRepeatability()
        if ~ensureData()
            return;
        end
        try
            levels = acousticbench.hha(state.data, ...
                'Container', ui.repeatContainerDropdown.Value, ...
                'Condition', ui.repeatConditionDropdown.Value);
        catch err
            setStatus(sprintf('Plot failed: %s', err.message));
            return;
        end
        sd = nanstd(levels, 0, 4);          % nFreq x nDevice x nSubject
        nFrequency = size(sd, 1);
        medianSd = NaN(nFrequency, 1);
        p95Sd = NaN(nFrequency, 1);
        for f = 1:nFrequency
            values = reshape(sd(f, :, :), [], 1);
            values = values(isfinite(values));
            if isempty(values)
                continue;
            end
            medianSd(f) = median(values);
            p95Sd(f) = localQuantile(values, 0.95);
        end
        freq = state.data.frequency;
        cla(ui.repeatAxes);
        semilogx(ui.repeatAxes, freq, medianSd);
        hold(ui.repeatAxes, 'on');
        semilogx(ui.repeatAxes, freq, p95Sd, '--');
        hold(ui.repeatAxes, 'off');
        legend(ui.repeatAxes, {'median', '95th percentile'}, 'Location', 'northwest');
        configureAxes(ui.repeatAxes, 'Frequency [Hz]', 'Reinsertion SD [dB]', ...
            sprintf('Within-subject reinsertion SD - %s', ui.repeatContainerDropdown.Value));
        state.plottedName = sprintf('acousticbench_repeatability_%s', ...
            ui.repeatContainerDropdown.Value);
        state.plottedTable = table(freq, medianSd, p95Sd, ...
            'VariableNames', {'FrequencyHz', 'MedianSdDb', 'P95SdDb'});
        band = freq >= 500 & freq <= 4000;
        ui.repeatInfoLabel.Text = sprintf( ...
            'Median SD (0.5-4 kHz): %.2f dB; 95th percentile: %.2f dB', ...
            median(medianSd(band & isfinite(medianSd))), ...
            median(p95Sd(band & isfinite(p95Sd))));
        setStatus('Plotted reinsertion repeatability.');
    end

    function onPlotThreshold()
        if ~ensureData()
            return;
        end
        familyIndex = find(strcmp(familyLabels(ui.devices), ui.thresholdFamilyDropdown.Value), 1);
        family = ui.devices(2 * familyIndex - 1).family;
        codes = [ui.devices(strcmp({ui.devices.family}, family)).code];
        try
            T = acousticbench.thresholdTable(state.data, ...
                'Statistic', ui.thresholdStatisticDropdown.Value, ...
                'DeviceCodes', codes);
        catch err
            setStatus(sprintf('Plot failed: %s', err.message));
            return;
        end
        referenceRows = strcmp(T.Condition, 'reference');
        measurementRows = strcmp(T.Condition, 'measurement');
        cla(ui.thresholdAxes);
        hold(ui.thresholdAxes, 'on');
        semilogx(ui.thresholdAxes, T.FrequencyHz(referenceRows), ...
            T.ValueDbv(referenceRows), 'o-');
        semilogx(ui.thresholdAxes, T.FrequencyHz(measurementRows), ...
            T.ValueDbv(measurementRows), 's-');
        hold(ui.thresholdAxes, 'off');
        legend(ui.thresholdAxes, {'reference', 'measurement'}, 'Location', 'southwest');
        configureAxes(ui.thresholdAxes, 'Frequency [Hz]', 'Threshold [dBV]', ...
            sprintf('%s thresholds (%s)', ui.thresholdFamilyDropdown.Value, ...
            ui.thresholdStatisticDropdown.Value));
        state.plottedName = sprintf('acousticbench_threshold_%s', family);
        state.plottedTable = T;
        ui.thresholdInfoLabel.Text = sprintf('%d rows, %s statistic', ...
            height(T), ui.thresholdStatisticDropdown.Value);
        setStatus('Plotted hearing thresholds.');
    end

    function refreshValidationTab()
        T = acousticbench.structuralValidityTable();
        cellData = [T.Container, num2cell(T.DeviceCode), T.Family, ...
            T.Coupling, T.Condition, num2cell(T.StructurallyValid), T.Rationale];
        ui.validationTable.Data = cellData;
        state.validationTable = T;
        if isempty(state.data)
            ui.validationSummary.Value = { ...
                'Load Data.mat to populate the measured-NaN session summary.'};
            return;
        end
        data = state.data;
        containers = {'M_ha2edM', 'M_ha2edR', 'M_ha2haf', 'M_ls2edM', ...
            'M_ls2edR', 'M_thr_ha', 'M_REUR'};
        lines = {'Measured-NaN (invalid) sessions per container:', ''};
        for k = 1:numel(containers)
            key = containers{k};
            nInvalid = nnz(data.nanSession.(key));
            nStructural = nnz(~data.structural.(key)(:));
            lines{end + 1} = sprintf( ...
                '  %-9s : %2d invalid sessions, %2d structurally invalid device codes', ...
                key, nInvalid, nStructural); %#ok<AGROW>
        end
        lines{end + 1} = '';
        lines{end + 1} = 'Measured NaNs and structurally invalid values are excluded, never imputed.';
        ui.validationSummary.Value = lines;
    end

    function deviceCodes = selectedDeviceCodes()
        devicesTable = ui.devices;
        switch ui.subsetDropdown.Value
            case 'earmolds'
                deviceCodes = [devicesTable([devicesTable.isEarmold]).code];
            case 'domes'
                deviceCodes = [devicesTable([devicesTable.isDome]).code];
            otherwise
                deviceCodes = [devicesTable.code];
        end
    end

    function name = deviceLabelForCode(code)
        index = find([ui.devices.code] == code, 1);
        if isempty(index)
            name = sprintf('Code %d', code);
        else
            name = ui.devices(index).shortLabel;
        end
    end

    function tf = ensureData()
        tf = ~isempty(state.data);
        if ~tf
            setStatus('Load Data.mat first.');
        end
    end

    function onExportPng()
        [fileName, folder] = uiputfile({'*.png', 'PNG image (*.png)'}, ...
            'Save figure as', fullfile(pwd, [state.plottedName '.png']));
        if isequal(fileName, 0)
            return;
        end
        axesHandle = ui.dataAxes;
        if ~isempty(ui.tabGroup.SelectedTab)
            switch ui.tabGroup.SelectedTab.Title
                case 'Frequency Response'
                    axesHandle = ui.frequencyAxes;
                case 'Acoustic Feedback'
                    axesHandle = ui.feedbackAxes;
                case 'Repeatability'
                    axesHandle = ui.repeatAxes;
                case 'Hearing Threshold'
                    axesHandle = ui.thresholdAxes;
                otherwise
                    axesHandle = ui.dataAxes;
            end
        end
        try
            exportgraphics(axesHandle, fullfile(folder, fileName), 'Resolution', 150);
        catch err
            setStatus(sprintf('PNG export failed: %s', err.message));
            return;
        end
        setStatus(sprintf('Saved %s', fullfile(folder, fileName)));
    end

    function onExportCsv()
        if isempty(state.plottedTable)
            setStatus('Nothing to export yet - plot a curve first.');
            return;
        end
        [fileName, folder] = uiputfile({'*.csv', 'CSV table (*.csv)'}, ...
            'Save table as', fullfile(pwd, [state.plottedName '.csv']));
        if isequal(fileName, 0)
            return;
        end
        try
            writetable(state.plottedTable, fullfile(folder, fileName));
        catch err
            setStatus(sprintf('CSV export failed: %s', err.message));
            return;
        end
        setStatus(sprintf('Saved %s', fullfile(folder, fileName)));
    end

    function setStatus(text)
        ui.statusLabel.Text = text;
        drawnow limitrate;
    end
end

% =======================================================================
function configureAxes(ax, xLabel, yLabel, titleText)
ax.XScale = 'log';
ax.XLabel.String = xLabel;
ax.YLabel.String = yLabel;
ax.Title.String = titleText;
ax.XGrid = 'on';
ax.YGrid = 'on';
ax.Box = 'on';
end

% =======================================================================
function label = addGridLabel(parent, text, row)
% Create a grid-layout label in the given row (local helper; avoids chained
% property assignment on a function-call result, which MATLAB rejects).
label = uilabel(parent, 'Text', text);
label.Layout.Row = row;
end

% =======================================================================
function labels = familyLabels(devices)
families = unique({devices.familyLabel}, 'stable');
labels = families;
end

% =======================================================================
function labels = deviceLabels(devices)
n = numel(devices);
labels = cell(1, n);
for k = 1:n
    labels{k} = sprintf('%02d - %s', devices(k).code, devices(k).label);
end
end

% =======================================================================
function names = makeValidNames(labels)
names = matlab.lang.makeValidName(labels);
names = matlab.lang.makeUniqueStrings(names);
end

% =======================================================================
function q = localQuantile(values, probability)
values = sort(values(:));
n = numel(values);
if n == 1
    q = values(1);
    return;
end
position = probability * (n - 1) + 1;
lowerIndex = max(floor(position), 1);
upperIndex = min(ceil(position), n);
fraction = position - lowerIndex;
q = (1 - fraction) * values(lowerIndex) + fraction * values(upperIndex);
end
