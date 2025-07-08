function unpackRotaryData(fname,tfname,dbasename,plotON)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%unpackRotaryEncoder
%Gerard Joey Broussard, PNI 20201016
%
%Utility for taking data from the arduino-read rotary encoder to package it
%as a matrix for inclusion in a database
%
% Inputs:
%   fname - filename of the rotary csv to analyze
%   tfname - filename for analyzed eyelid position
%   dbasename - name of .mat file containing database
%   plotON - toggles qc plots. Default true
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Handling inputs
if nargin == 2
    dbaseON = 0;
    plotON = 1;
    close all;
elseif nargin == 3
    dbaseON = 1;
    plotON = 1;
elseif nargin == 4
    dbaseON = 1;
end
%% Read in and set up data
%Get animal and session identifiers
[~,file] = fileparts(fname);
identifiers = strsplit(file,'_');
animalID = identifiers{1};
sessionDate = identifiers{2};

%Parse rotary data
[millis,event,value,meta] = importRigEvents(fname);
try
    CSdur = str2num(meta.CSdur);
catch
    help =1;
end
USdur = str2num(meta.USdur);
preCSdur = str2num(meta.preCSdur);
trialDur = str2num(meta.trialDur);

%Get rotary, start, and trial type data
rotIdxs = find(event == 'rotary');
startIdxs = [find(event == 'startTrial');inf];
trialTypes = {'CS','US','CS_US'};theseTrialTypes = event(ismember(event,trialTypes));
UStypes = nominal;UStypes(theseTrialTypes=='CS') = 'none';
stillFlags = {'Still','NotStill'};theseStillFlags = event(ismember(event,stillFlags));
try
    UStypes(theseTrialTypes~='CS') = event(ismember(event,{'bigUSon','medUSon','smallUSon'}));
catch
    UStypes(1);
end
CRcount = value(event=='CRcount');

millis_mat = [];
value_mat = [];
millisUp = 0:trialDur;%upsampling to millisecond

%Get the newFile trigger times for 2P
fStartIdx = [find(event == '2Pon');arrayfun(@(x)...
    find(event=='newFile'&[1:length(event)]'<x,1,'last'),...
    startIdxs(2:end-1))];
newFileTimes = millis(fStartIdx);

%factor to convert from optical poles to distance
circ = 15.24*pi;%cm/rev; 14cm is diameter of Ruzzy wheel, 15.24 for the Aeromat roller
poles = 2000*4;%optical edges/rev; 2000 for the CALT encoder (GHS3806G2000BMP526-RE)
pole2cm = circ/poles;%cm/optical poles

%% Pack rotary data to convenient variables to plot
for i = 1:length(startIdxs)-1
    goodIdxs = rotIdxs(rotIdxs>startIdxs(i) & rotIdxs<startIdxs(i+1));
    thisTime = millis(goodIdxs(2:end))-millis(startIdxs(i));
    %first millis through, grab the rotary encoder sampling rate
    if i==1
        pollRate = mean(diff(thisTime));
    end
    thisVals = value(goodIdxs(2:end))*pole2cm/(pollRate/1000);%convert poles/sample to cm/s
    thisVals = interp1(thisTime,thisVals,millisUp,'linear','extrap');
    baseTime = millisUp>preCSdur-100 & millisUp<preCSdur;
    thisVals = thisVals -mean(thisVals(baseTime));
    millis_mat = nancat(1,millis_mat,thisTime);
    value_mat = nancat(1,value_mat,thisVals);
    
end

%% For the eyeblink trace
if ~isempty(tfname)
    load(tfname);
end

%% Pack out data to dbase
if dbaseON
    if exist(dbasename,'file')
        load(dbasename)
        newIdx = length(dbase)+1;
        %Check if file already loaded and plot state
        currentFnames = {dbase.fname};
    else
        dbase = struct;
        newIdx = 1;
        currentFnames = [];
    end

    
    if any(strcmp(fname,currentFnames))&&~plotON
        return;
    else
        %Pack in new dbase element and save
        dbase(newIdx).animalID = animalID;
        dbase(newIdx).fname = fname;
        dbase(newIdx).trace_fname = tfname;
        dbase(newIdx).sessionDate = sessionDate;
        dbase(newIdx).trialTypes = theseTrialTypes;
        dbase(newIdx).UStypes = UStypes';
        dbase(newIdx).CRcount = CRcount;
        dbase(newIdx).time_rotary = millisUp';
        dbase(newIdx).speed_rotary = value_mat';
        if ~isempty(tfname)
            dbase(newIdx).time_eye = eyetime';
            dbase(newIdx).eyetrace_pos = eyetraces';
        end
        dbase(newIdx).newFileTimes = newFileTimes;
        dbase(newIdx).stillFlags = theseStillFlags;
        dbase(newIdx).meta = meta;

        save(dbasename,'dbase');
    end
end

%% Plots
if plotON
    %QC plots
    figure;
    plot(diff(millis(rotIdxs)))
    xlabel('read number')
    ylabel('difference in consecutive read milliss')
    figure;
    plot(range(millis_mat,2));
    ylabel('Range for millis valueue at each step')
    xlabel('millis step')

    %Plots of session performance
    hands = [];linStyles = {':','--','-'};
    for i = 1:length(trialTypes)
        if sum(theseTrialTypes==trialTypes(i))==0
            continue;
        end
        thisValue_mat = value_mat(theseTrialTypes==trialTypes(i),:);
        if i==1;f1 = figure('Name','Comparing trialTypes');hold on;end
        figure(f1);
        
        h = plot(millisUp-str2num(meta.preCSdur),nanmean(thisValue_mat,1),...
            'linestyle',linStyles{i},'color','k');
        hands = [hands,h];
        figure;
        subplot(2,1,1);hold on;
        imagesc(thisValue_mat);axis tight;colormap(gray);c = colorbar;c.Label.String = 'speed (cm/s)';
        ylabel('trial');title([meta.animalID,meta.date,trialTypes(i)]);
        plot([preCSdur,preCSdur],ylim,'r--');
        plot([preCSdur+(CSdur-USdur),preCSdur+(CSdur-USdur)],ylim,'b--');
        posImg = get(gca,'Position');
        set(gca,'xticklabels',[],'fontsize',12)

        %Add on big vs. small US indicator at margin for CS_US only
        if any(strcmp(trialTypes(i),{'CS_US','US'}))
            hold on;
            UStype = UStypes(theseTrialTypes==trialTypes(i));
            hBig = plot(ones(1,length(find(UStype=='bigUSon'))),find(UStype=='bigUSon'),...
                'r*','markersize',3);
            hSmall = plot(ones(1,length(find(UStype=='smallUSon'))),find(UStype=='smallUSon'),...
                'g^','markersize',3);
            legend([hBig,hSmall],{'no CR trials','CR trials'});
            percSmall = [trialTypes(i),'CRtrial% = ',num2str(sum(UStype=='smallUSon')/length(UStype))];
        end

        subplot(2,1,2);hold on;
        shadedErrorBar(millisUp,thisValue_mat,{@nanmean,@nanstd});
        plot([preCSdur,preCSdur],ylim,'r--');
        ylims = ylim;text(preCSdur,ylims(2)+(ylims(2)-ylims(1))/20,'cs','color','r','HorizontalALignment','right')
        plot([preCSdur+(CSdur-USdur),preCSdur+(CSdur-USdur)],ylim,'b--');
        text(preCSdur+(CSdur-USdur),ylims(2)+(ylims(2)-ylims(1))/20,'us','color','b','HorizontalALignment','left')
        xlabel('millis from CS onset (ms)');ylabel('speed (cm/s)');title(sprintf('Session average\n'))
        %posPlot = get(gca,'Position');
        %set(gca,'Position',[posPlot(1:2),posImg(3),posPlot(4)]);
        set(gca,'xticklabels',compose('%0.0f',get(gca,'xtick')-preCSdur),'fontsize',12);
    end
    figure(f1);
    US_start = str2num(meta.CS_USinterval);
    plot([0,0],ylim,'r--');
    plot([US_start,US_start],ylim,'b--');
    legend(hands,trialTypes);
    xlabel('time (msec)');
    ylabel('speed (cm/s)');
    title([meta.animalID,meta.date,'trial type comparison']);
end