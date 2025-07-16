# -*- coding: utf-8 -*-
"""
Created on Fri Dec 31 09:14:13 2021

This utility creates converts movies captured by the assocLearnRig system
to viewable .mp4. CS and US epochs are indicated by a white then black
square embedded in the movie's upper right corner.

@author: gerardjb
"""

from tkinter import Tk, filedialog
import glob
import imageio
import pickle
import numpy as np
import cv2
import os
import csv

#Path and files to make movies for
root = Tk()
root.withdraw()
root.attributes('-topmost', True)
path = filedialog.askdirectory()
files = sorted([(d,f) for d,_,fs in os.walk(path) for f in fs if f.endswith('.data')])
im_files = [os.path.join(*i) for i in files]
files = sorted([(d,f) for d,_,fs in os.walk(path) for f in fs if f.endswith('.txt')])
txt_files = [os.path.join(*i) for i in files]

#Get names and display available files
names = [os.path.splitext(os.path.split(f)[-1])[0] for f in im_files]
print('Available datasets:')
for idx,n in enumerate(names):
    print(f'\t{idx}\t{n}')

#%% function to convert mjpg to np array
def mjpg2array(filename):   
    #Open and unpickle the bytes file
    filehand = open(filename,'rb')
    stream = []
    while 1:
        try:
            stream.append(pickle.load(filehand))
        except EOFError:
            break
    filehand.close()
    #Flatten stream and separate out timestamps
    stream = [x for l in stream for x in l]
    lists = [list(t) for t in zip(*stream)]
    ts = np.array(lists[0])*1000
    stream = lists[1]
    nIm = len(stream)
    
    #Reading through the binary file to parse image data
    idx = 0 #for buidling the np image array
    for img in stream:
        #grab frame start and end on hex stream
        a = img.find(b'\xff\xd8')
        b = img.find(b'\xff\xd9')
        if a != -1 and b != -1:
            jpg = img[a:b+2]
            #stream = stream[b+2:]
            data = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            
            if idx==0:
                #For plot of line scan
                sizeWH = data.shape
                #Full output array
                mov = np.empty([int(sizeWH[0]),int(sizeWH[1]),nIm],dtype=np.uint8)
                mov[:,:,0] = data
            else:
                mov[:,:,idx] = data
            idx += 1
        elif a==-1 or b==-1:
            pass
    
    # permute the data to put time element first
    imArray = np.transpose(mov,(2,0,1))
    return imArray,ts

#%% selecting and opening files to make into movies
#Grab first row headers from txt_files, parse to dictionary
with open(txt_files[0]) as txtfilehand:
    reader=csv.reader(txtfilehand)
    headers = next(reader)
headers = dict(x.split('=') for x in headers[0].split(';') if '=' in x)
txtfilehand.close()

#Loop over and write movies
for file,name in zip(im_files,names):
    #parse bytes to np array
    imArray,time = mjpg2array(file)
    
    # only apply CS/US stamps for non-ITI files
    if 'ITI' not in name:
        #Make a subarray corresponding to highlighted trace period
        csTime = float(headers['preCSdur'])  # millis at CS start
        csusInt = float(headers['CS_USinterval'])  # CS alone length
        usDur = float(headers['USdur'])  # US duration
        pad = [300,300]
        timeEnds = [-pad[0]+csTime, pad[1]+csTime+csusInt]
        goodFrames = (time>timeEnds[0]) & (time<timeEnds[1])
        #Stamps for CS and US
        csStamp = np.zeros(np.shape(imArray[0]),dtype=np.uint8)
        csStamp[0:10,0:10] = 255
        usStamp = np.ones(np.shape(imArray[0]),dtype=np.uint8)
        usStamp[0:10,0:10] = 0
        csEnds = [csTime, csTime+csusInt+usDur]
        usEnds = [csTime+csusInt, csTime+csusInt+usDur]
        for a in np.where((time>=csEnds[0]) & (time<=csEnds[1])):
            imArray[a] = imArray[a]*usStamp + csStamp
        for b in np.where((time>=usEnds[0]) & (time<=usEnds[1])):
            imArray[b] = imArray[b]*usStamp
    else:
        # For ITI files, include all frames without stamping
        goodFrames = np.arange(len(time))
    
    #write to mp4
    imSubArray = imArray[goodFrames]
    if not os.path.exists(os.path.join(path,'sampleMovs')):
        os.makedirs(os.path.join(path,'sampleMovs'))
    im_fileOut = os.path.join(path,'sampleMovs',name+'.mp4')
    imageio.mimwrite(im_fileOut,imSubArray)
