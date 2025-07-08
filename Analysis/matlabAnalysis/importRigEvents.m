function [millis, event, value,metadata] = importRigEvents(filename, dataLines)
%importRigEvents Import events record from a rig
%  [MILLIS, EVENT, VALUE] = importRigEvents(FILENAME) reads data from text
%  file FILENAME for the default selection.  Returns the data as column
%  vectors.
%
%  [MILLIS, EVENT, VALUE] = importRigEvents(FILE, DATALINES) reads data for
%  the specified row interval(s) of text file FILENAME. Specify
%  DATALINES as a positive scalar integer or a N-by-2 array of positive
%  scalar integers for dis-contiguous row intervals.
%
%  Example:
%  [millis, event, value] = importRigEvents("JB62_20200904_112740_s1.txt", [3, Inf]);


%% Input handling

% If dataLines is not specified, define defaults
if nargin < 2
    dataLines = [3, Inf];
end

%% Import the metadata
metadata = struct;
%Input animal ID
[~,file] = fileparts(filename);
animalID = strtok(file,'_');
metadata = setfield(metadata,'animalID',animalID);
%Strip rest of metadata
fid = fopen(filename);meta = string(textscan(fid,'%s',1));fclose(fid);
meta = strsplit(meta,';');

for i = 1:length(meta)
    thisMeta = strsplit(meta(i),'=');
    try
        metadata = setfield(metadata,thisMeta(1),thisMeta(2));
    catch
        sprintf('One field from %s did not populate',filename)
    end
end

%% Setup the Import Options and import the data
opts = delimitedTextImportOptions("NumVariables", 3);

% Specify range and delimiter
opts.DataLines = dataLines;
opts.Delimiter = ",";

% Specify column names and types
opts.VariableNames = ["millis", "event", "value"];
opts.VariableTypes = ["double", "categorical", "double"];

% Specify file level properties
opts.ExtraColumnsRule = "ignore";
opts.EmptyLineRule = "read";

% Specify variable properties
opts = setvaropts(opts, "event", "EmptyFieldRule", "auto");

% Import the data
tbl = readtable(filename, opts);

%% Convert to output type
millis = tbl.millis;
event = tbl.event;
value = tbl.value;

end