####This creates the GUI which subsequently instantiates all hardware objects
import PySimpleGUI as sg
from picamera import PiCamera
import RPi.GPIO as GPIO
import pivideostream as pvid
import cv2
import numpy as np
import time
import sys
import signal
from arduinoRig import arduinoRig

#For realtime visualizations
from matplotlib import cm
import matplotlib.pyplot as pl
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, FigureCanvasAgg
from matplotlib.figure import Figure
from random import randint

####### LED PWM SETUP #######
LED_PIN = 18               # BCM pin for LED
GPIO.setmode(GPIO.BCM)     # use Broadcom pin numbering
GPIO.setup(LED_PIN, GPIO.OUT)
led_pwm = GPIO.PWM(LED_PIN, 1000)  # 1 kHz PWM
led_pwm.start(0)                  # start at 0% duty (off)

# GLOBAL VARS/plotting functions
n2show = 4;
cmap_r = np.zeros((n2show,4));cmap_r[:,0]=np.linspace(0.1,1,n2show);cmap_r[:,3]=1#
cmap_e = np.zeros((n2show,4));cmap_e[:,1]=np.linspace(0.1,1,n2show);cmap_e[:,2]=np.linspace(0,1,1,n2show);cmap_e[:,3]=1
def draw_figure(canvas, figure, loc=(0, 0)):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg
    
def update_plot(ax,vls=np.nan,rot_time=np.nan,rot=np.nan,eb_time=np.nan,eb=np.nan,h=np.nan,vh=np.nan):#Adding whichever elements are available to the plot    
    #Handling vertical line stimulus plots
    ymin,ymax = ax.get_ylim()
    if not vh:
        vh = [ax.vlines(vls[0],ymin,ymax,linestyle='--',color='black')]
        vh.append(ax.vlines(vls[0]+vls[1]-vls[2],ymin,ymax,linestyle='--',color='black'))
        vh.append(ax.vlines(vls[0]+vls[1],ymin,ymax,linestyle='--',color='black'))
        
    if isinstance(rot, np.ndarray) and rot.size > 0:
        rmax, rmin = rot.max(), rot.min()
        if rmax > ymax or rmin < ymin:
            [v.remove() for v in vh]
            ymax, ymin = max(rmax, ymax), min(rmin, ymin)
            vh = [ax.vlines(vls[0], ymin, ymax, linestyle='--', color='black')]
            vh.append(ax.vlines(vls[0] + vls[1] - vls[2], ymin, ymax, linestyle='--', color='black'))
            vh.append(ax.vlines(vls[0] + vls[1], ymin, ymax, linestyle='--', color='black'))
     
    #Handling the rotary plots    
    if not h and not np.isnan(rot).all():
        h = [ax.plot(rot_time,rot)]
    elif not np.isnan(rot).all():
        h.append(ax.plot(rot_time,rot))
    
    if len(h)>n2show:
        h[0][0].remove()
        h.remove(h[0])
        [z[0][0].set(color=z[1]) for z in zip(h,cmap_r)]
    else:
        [z[0][0].set(color=z[1]) for z in zip(h,cmap_r)]
        
    return h,vh
    
def clear_plot(ax):
    #Clear plot and axis handles
    ax.cla()
    ax.grid()
    h=[];vh=[]
    return h,vh
    

    
####Build the GUI####
sg.theme("DarkAmber")#BluePurple also has a nice asthetic

###Define the window layout
camera_layout = [
    ##Camera control and display panels
    [],
    [sg.Image(filename="", key="-IMAGE-",size=(300,240))],
    [sg.Button("Stream",size=(9,1)),sg.Button("End Stream",size=(9,1)),
    sg.Button("Save Stream",size=(9,1)),sg.Button("End Recording",size=(9,1))],
]
trial_layout = [
    ##Arduino, file name, and session controls
    [sg.Button("Start Session",size=(14,1),button_color=('white','springgreen4')),
     sg.Button("Stop Session",size=(14,1),button_color=('white','firebrick3')),
     sg.Text("Trial",size=(18,1), key='trialNum')],
    [
        sg.Text("Animal ID"),
        sg.Input(size=(25,1),key="Animal"),
        sg.Button('Set',bind_return_key=True)
    ],
    [
        sg.Text("Session type"),
        sg.Radio('DTSC',"RADIO",default=True,key="DTSC"),
        sg.Radio('DEC',"RADIO",key="DEC")
    ],
    [sg.HSeparator()],
    [sg.Column([
        [sg.T("Number trials"),sg.Input(size=(10,1),key="numTrial",default_text="110")],
        [sg.T("ITI low (ms)"),sg.Input(size=(10,1),key="ITIlow",default_text="1000")],
        [sg.T("Percent CS"),sg.Input(size=(10,1),key="percentCS",default_text="10")],
        [sg.T("CS duration (ms)"),sg.Input(size=(10,1),key="CSdur",default_text="250")],
        [sg.T("Pre-CS duration (ms)"),sg.Input(size=(10,1),key="preCSdur",default_text="200")]
    ]),
    sg.Column([
        [sg.T("Trial duration (ms)"),sg.Input(size=(10,1),key="trialDur",default_text="1000")],
        [sg.T("ITI high (ms)"),sg.Input(size=(10,1),key="ITIhigh",default_text="1500")],
        [sg.T("Percent US"),sg.Input(size=(10,1),key="percentUS",default_text="0")],
        [sg.T("US duration (ms)"),sg.Input(size=(10,1),key="USdur",default_text="30")]
    ],vertical_alignment='top')],
    [sg.Button("Upload to Microcontroller"),sg.Button("Current Microcontroller settings")],
    [sg.Text("Background LED intensity (0-100)"),
     sg.Input(key="LED_INTENSITY", size=(5,1), default_text="0"),
     sg.Button("Set LED"), sg.Button("LED Off")]
]

graph_layout = [
    [sg.Canvas(size=(300, 200),
        key='graph')]
]

exit_layout = [
    [sg.Button("End Program",size=(30,2))]
]

##full GUI layout
layout = [
    [
        [sg.Frame("Camera controls",camera_layout,title_location='n',element_justification='c'),
        sg.Frame("Arduino session controls",trial_layout,title_location='n',element_justification='l')],
        [sg.Frame("Graph test",graph_layout,title_location='n',element_justification = 'c'),
        sg.Frame("Exit test",exit_layout)]
    ]
]

####Create the window, arduinoRig, and piStream####
window = sg.Window("Associative Learning control GUI", layout)
rig = arduinoRig()
event, values = window.read(timeout=0)
current_trial = rig.trial['trialNumber']
window['trialNum'].update("Trial number = "+str(current_trial))
vs = None

# draw the initial plot in the window
graph_elem = window['graph']
graph = graph_elem.TKCanvas
fig = Figure(figsize=[4,3])
ax = fig.add_subplot(111)
ax.set_xlabel("time")
ax.set_ylabel("some stuff (A.U.)")
ax.grid()
fig_agg = draw_figure(graph, fig)
colors = cm.jet(np.linspace(0,1,5))#We will ultimately show up to five traces at once
vls = [float(values['preCSdur']),float(values['CSdur']),float(values['USdur'])]
rot=np.nan;rot_time=np.nan;eb=np.nan;eb_time=np.nan;h=[];vh=[];

####Handling the GUI, rig, and piCamera####
#Loop booleans and variables
streaming = False#state of camera output
frame = None#current frame for output to GUI video
dispNow = True#to display current fame on GUI video
lastpicTime = 0#timing when next frame should be output to GUI video
#What to do if keyboard interrupt called
def signal_handler(sig, frame):
    if vs is not None:
        vs.end()
        print("vs.end()")
    rig.end()
    print("\nProgram ended")
    sys.exit(0)
signal.signal(signal.SIGINT,signal_handler)

####GUI read loop
while True:

    #Update the trial counter where necessary
    if current_trial != rig.trial['trialNumber']:
        current_trial = rig.trial['trialNumber']
        window['trialNum'].update("Trial Number = "+str(current_trial))

    #Get whatever input the user applied to GUI
    event, values = window.read(timeout=0)
    
    #If the camera is on, check if we need to update GUI frame
    if streaming:
        now = time.perf_counter()
        dispTime = now - lastpicTime
        if dispTime>0.05:
            frame = vs.read()
            lastpicTime = time.perf_counter()
            
    #Here tell the GUI to look for a flag to update the current plot
    if rig.data_handler.rotary_ready:
        rot,rot_time = rig.data_handler.get_rotary()
        rig.data_handler.rotary_ready = False
        h,vh = update_plot(ax,vls,rot=rot,rot_time=rot_time,h=h,vh=vh)
        fig_agg.draw()
    
    ##Button options, left panel
    if event == "End Program" or event == sg.WIN_CLOSED:
        break
    elif event == "Stream":
        if not streaming:
            if vs is None:
                vs = pvid.piCamHandler()
            else:
                vs.reset_cam()
            streaming = True
            print("Start stream")
        else:
            print("Camera already streaming!")
    elif event == "End Stream":
        if vs is not None:
            vs.endStream()
        streaming = False
        frame = None
        print("End Stream")
    elif event == "Save Stream":
        if streaming and not vs.saving.value:
            vs.guiStartRecording()
            print("Save Stream")
    elif event == "End Recording":
        if streaming and vs.saving.value:
            vs.guiStopRecording()
            print("End Recording")
    ##Button options right panel
    elif event == "Start Session":
        rig.startSession()
        h,vh = clear_plot(ax)
        h,vh = update_plot(ax,vls,h=h,vh=vh)
        fig_agg.draw()
        while not rig.fnameReady:
            pass
        fStub = rig.getFstub()
        if vs is not None:
            vs.passFstub(fStub)
    elif event == "Stop Session":
        rig.stopSession()
    elif event == "Set":
        rig.animalID = values['Animal']
        print("Set animalID: ",values['Animal'])
    elif event == "Upload to Microcontroller":
        if values['DTSC']:
            rig.settrial('isDTSC',1)
        elif values['DEC']:
            rig.settrial('isDTSC',0)
        for item in values.items():
            if item[0] not in ['Animal','DTSC','DEC','graph']:
                rig.settrial(item[0],item[1])
                time.sleep(0.001)
                
        vls = [float(values['preCSdur']),float(values['CSdur']),float(values['USdur'])]
    elif event == "Current Microcontroller settings":
        rig.GetArduinoState()
    
    # LED controls
    elif event == "Set LED":
        try:
            intensity = float(values['LED_INTENSITY'])
            intensity = max(0, min(100, intensity))
            led_pwm.ChangeDutyCycle(intensity)
            print(f"LED intensity set to {intensity}%")
        except ValueError:
            print("Invalid intensity value")
    elif event == "LED Off":
        led_pwm.ChangeDutyCycle(0)
        print("LED turned off")

    ##Process and display the current frame capture in GUI if streaming
    if streaming and frame is not None:
        if len(frame)>0:
            data = cv2.resize(cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_GRAYSCALE),(300,240))
            imgbytes = cv2.imencode('.png',data)[1].tobytes()
            window["-IMAGE-"].update(data=imgbytes)
        frame = None
    
    time.sleep(0.005)
    
##Do this when the program is ended
window.close()
if vs is not None:
    vs.end()
    print("vs.end()")
rig.end()
print("rig.end()")
print('Program ended')
