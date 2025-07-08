function DBbuilder_rotary
%Select the directory to process
close all
%d = uigetdir([],'Pick a root directory');
d = 'Z:\Joey\RawImaging\20240415_JB250-60_Tsc1_DTSC';
files = dir(fullfile(d,'**\*.*'));
files = arrayfun(@(x) fullfile(x.folder,x.name),files,'UniformOutput',false);
trace_files = files(endsWith(files,'traces.mat'));
files = files(endsWith(files,'.txt'));
%Name of file to hold the database
dbasename = fullfile(d,'dbase_test.mat');

%Load dbase to see if file has already been processed
if isfile(dbasename)
    load(dbasename);
    currentFnames = nominal({dbase.fname});
else
    currentFnames = nominal([]);
end


%Draw each session in directory into database
for i= 1:length(files)
    %Only selecting the text files for analysis
    if ~any(files{i}==currentFnames)
        try
            unpackRotaryData(files{i},trace_files{i},dbasename,0);
        catch
            try
                unpackRotaryData(files{i},[],dbasename,0);
            catch
                x = 1;
            end
        end
        
    end

end


%Query data base for a few salient features
close all
load(dbasename)
%Cull short sessions
sessLengths = arrayfun(@(x) length(x.trialTypes),dbase);
badIdx = sessLengths~=mode(sessLengths);
dbase(badIdx) = [];

%Prep plot loop
animalIDs = nominal({dbase.animalID});
uniAnimal = unique(animalIDs);
colors = linspecer(length(uniAnimal));markers = repmat({'*'},length(uniAnimal),1);
f1 = figure('Name','CR percent');
f2 = figure('Name','Naive mouse velocity CS+US');
f3 = figure('Name','Naive mouse velocity CS');
f4 = figure('Name','Trained mouse velocity CS+US');
f5 = figure('Name','Trained mouse velocity CS');
fs = [f1,f2,f3,f4,f5];
allCSUStrace = zeros(length(dbase(1).time_rotary),length(uniAnimal),2);
allCStrace = zeros(length(dbase(1).time_rotary),length(uniAnimal),2);
for i = 1:length(uniAnimal)
    %Plot for percent CR
    percCR = arrayfun(@(x)...
        sum((x.UStypes=='medUSon'|x.UStypes=='smallUSon')&x.trialTypes=='CS_US')/...
        sum(x.UStypes~='none'&x.trialTypes=='CS_US'),...
        dbase(animalIDs==uniAnimal(i)));
    figure(f1);hold on;
    plot(1:length(percCR),percCR,...
        'color',colors(i,:),'marker',markers{i});
    
    %Plot to compare response types
    timePoint = {'first','last'};
    for j = 1:2
        preCSdur = str2double(dbase(find(animalIDs==uniAnimal(i),1,'first')).meta.preCSdur);
        speed_rotary = dbase(find(animalIDs==uniAnimal(i),1,timePoint{j})).speed_rotary;
        speed_rotary = speed_rotary - repmat(mean(speed_rotary(preCSdur-10:preCSdur+10,:),1),size(speed_rotary,1),1);
        time = dbase(find(animalIDs==uniAnimal(i),1,timePoint{j})).time_rotary-preCSdur;
        trialTypes = dbase(find(animalIDs==uniAnimal(i),1,timePoint{j})).trialTypes;
        CS_UStrace = nanmean(speed_rotary(:,trialTypes=='CS_US'),2);
        allCSUStrace(:,i,j) = CS_UStrace;
        CStrace = nanmean(speed_rotary(:,trialTypes=='CS'),2);
        allCStrace(:,i,j) = CStrace;
        %Plot individual animal mean traces
        figure(fs(2*j));hold on;
        plot(time',CS_UStrace,...
            'color',colors(i,:));
        figure(fs(2*j+1));hold on;
        plot(time',CStrace,...
            'color',colors(i,:));
    end
    
end
%labels
figure(f1);
xlabel('Sessions (days)')
ylabel('CR (percent of total)')
legend(cellstr(uniAnimal));
trainingPoint = {'Naive','Latest training'};
for i = 1:2
    figure(fs(2*i));
    plot([0,0],ylim,'k--');plot([200,200],ylim,'k--');
    xlabel('time from CS (msec)')
    ylabel('Speed (cm/s)');
    set(gca,'xlim',[-50,300])
    title([trainingPoint{i},' trials (CS+US)'])
    figure(fs(2*i+1));
    plot([0,0],ylim,'k--');plot([200,200],ylim,'k--');
    xlabel('time from CS (msec)')
    ylabel('Speed (cm/s)');
    set(gca,'xlim',[-50,300],'fontsize',12)
    title([trainingPoint{i},' catch trials (CS only)'])
end

%Summary plot
figure;hold on;colors = {'k','r'};
hCSUS_N = shadedErrorBar(time',allCSUStrace(:,:,1)',...
    {@nanmean,@nanstd},{'color',colors{1}},1);
hCSUS_T = shadedErrorBar(time',allCSUStrace(:,:,2)',...
    {@nanmean,@nanstd},{'color',colors{2}},1);
plot([0,0],ylim,'k--');plot([200,200],ylim,'k--');
xlabel('time from CS (msec)')
ylabel('Speed (cm/s)');
title('Average training trials response')
legend([hCSUS_N.mainLine,hCSUS_T.mainLine],{'Day1','Final Day'});
set(gca,'xlim',[-10,240],'ylim',[-20,5],'fontsize',12)
end