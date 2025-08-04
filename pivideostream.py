

# Control of the camera
import picamera
from picamera import PiCamera
import io
import multiprocessing as mp
from queue import Empty
import ctypes
import RPi.GPIO as GPIO
import time
import pickle



   
class ImgOutput(object):
    #Object with write method that informs other threads when a frame is available
    def __init__(self,frame_buffer,finished,current_frame,triggerTime,saving,kill_flag):
        self.saving = saving
        self.frame_buffer = frame_buffer
        self.current_frame = current_frame
        self.triggerTime = triggerTime
        self.kill_flag = kill_flag
        self.buffer = io.BytesIO()
        self.finished = finished
        self.condition = mp.Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8') and not self.kill_flag.value:
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            ts = time.perf_counter()-self.triggerTime.value-0.02
            #self.camTS.value = time.perf_counter()
            size = self.buffer.tell()
            if size:
                self.buffer.seek(0)
                frame = self.buffer.read(size)
                self.current_frame.value = frame
                if self.saving.value:
                    self.frame_buffer.put([ts,frame])
                self.buffer.seek(0)
                time.sleep(0.001)
        self.buffer.write(buf)
       
    def flush(self):
        self.frame_buffer.close()
        self.frame_buffer.join_thread()
        self.finished.set()
   

class MovieSaver(mp.Process):
    #Handles the saving of movie data as a separate process called in picamhandler
    def __init__(self, fname, startSave, saving, frame_buffer, flushing, buffer_size=2000, min_flush=200,piStreamDone=None,kill_flag=None):#,triggerTime=None,camTS=None
        super(MovieSaver, self).__init__()
        self.daemon = True
           
        #Saving parameters
        self.fname = fname
        self.buffer_size = buffer_size
        self.min_flush = min_flush
       
        ##Inherited flags and containers
        self.saving = saving
        self.startSave = startSave
        self.frame_buffer = frame_buffer
        self.flushing = flushing
        self.piStreamDone = piStreamDone
        #self.triggerTime = triggerTime
        #self.camTS = camTS
        self.kill_flag = kill_flag

        #Process-specific
        self.saving_complete = mp.Value('b',True)
       
        self.start()
       
    def run(self):
        fi = None
        datalist = []
        while not self.kill_flag.value:
            if self.startSave.value:
                self.startSave.value = False
                self.saving_complete.value = False
                # Close previous file if somehow left open
                if fi is not None and not fi.closed:
                    fi.close()
                fi = open(self.fname.value, 'wb')
                datalist = []
   
            if not self.piStreamDone.value:
                # Accumulate frames and do partial flush when big enough
                while not self.frame_buffer.empty():
                    ts, frame = self.frame_buffer.get(block=False)
                    datalist.append((ts, frame))
                if fi is not None and len(datalist) >= self.min_flush:
                    pickle.dump(datalist, fi)
                    datalist = []
                    print('Wrote to file')
   
            if self.flushing.value and self.piStreamDone.value:
                # Final flush for this segment
                while not self.frame_buffer.empty():
                    ts, frame = self.frame_buffer.get(block=False)
                    datalist.append((ts, frame))
                if fi is not None and not fi.closed:
                    pickle.dump(datalist, fi)
                    fi.close()
                datalist = []
                self.saving_complete.value = True
                self.flushing.value = False
                print('Finished saving')
   
            time.sleep(0.001)
   
        # On kill/exit: flush remaining
        if fi is not None and not fi.closed:
            while not self.frame_buffer.empty():
                ts, frame = self.frame_buffer.get(block=False)
                datalist.append((ts, frame))
            if datalist:
                pickle.dump(datalist, fi)
            fi.close()
            self.saving_complete.value = True
       
           

class PiVideoStream(mp.Process):
    DEBOUNCE_SEC = 0.05
   
    def __init__(self,output=None,resolution=(160, 128),framerate=60,frame_buffer=None,finished=None,stream_flag=None,saving=None,sync_flag=None,startAcq=None,triggerTime=None,piStreamDone=None,kill_flag=None,**kwargs):
        #Note output could be an instantiation of ImgOutput or any file-type object
        #with a write method that returns each frame capture as the write
        super(PiVideoStream,self).__init__()
        self.daemon = True
       
        ##Initialize and set up the camera
        self.output = output
        self.frame_buffer = frame_buffer
        self.finished = finished
        self.camera = PiCamera()
        # set camera parameters
        self.camera.resolution = resolution
        self.camera.framerate = framerate
        self.camera.rotation = 0
        # consistent pictures and timing on timestamps
        self.camera.iso = 800
        time.sleep(1)
        self.camera.shutter_speed = self.camera.exposure_speed
        self.camera.exposure_mode = 'off'
        g = self.camera.awb_gains
        self.camera.awb_mode = 'off'
        self.camera.awb_gains = g
        self.camera.clock_mode = 'raw'
        #Setting up camera clock, outputs, and initial image annotation
        self.camera.start_recording(self.output, format='mjpeg')
        self.camera.annotate_background = picamera.Color('black')
        self.camera.annotate_text_size = 6
        self.camera.annotate_text = 'Not recording'
       
        ##For interacting with the save and GPIO processes
        #Shared processes inherited from parent
        self.stream_flag = stream_flag
        self.saving = saving
        self.startAcq = startAcq
        self.triggerTime = triggerTime
        self.piStreamDone = piStreamDone
        self.kill_flag = kill_flag
       
        ##Process-specific flags
        self.thread_complete = mp.Value('b',True)
        self.getSaveRead = mp.Value('b',False)
       
        # set optional camera parameters (refer to PiCamera docs)
        for (arg, value) in kwargs.items():
            setattr(self.camera, arg, value)
       
        self.start()
       
    def run(self):
        while not self.kill_flag.value:
            #Looking for GPIO or GUI to flip startAcq flag
            if self.startAcq.value:
                #Get time from trigger in ms
                triggerLatency = time.perf_counter() - self.triggerTime.value
                #If longer than one frame grab, we entered between grabs-> subtract one frame time off
                if triggerLatency>1/self.camera.framerate:
                    self.triggerTime.value = self.triggerTime.value - 1/self.camera.framerate
                self.startAcq.value = False
                self.saving.value = True
                self.piStreamDone.value = False
               
            if not self.saving.value and not self.startAcq.value:
                #reset flags
                self.piStreamDone.value = True
            time.sleep(0.001)
           
        self.piStreamDone.value = True
       
       
class piCamHandler():
    def __init__(self,resolution=(160,128),framerate=60): #,sync_flag=None
        #Params for picamera
        self.resolution = resolution
        self.framerate = framerate
       
        #Shared variables for acquisition and saving processes
        self.manager = mp.Manager()
        self.fname = self.manager.Value(ctypes.c_char_p, time.strftime("%Y%m%d") + '_'+ time.strftime("%H%M%S") + '_'+ 'rig.data')
        self.fStub = self.manager.Value(ctypes.c_char_p,"noStub")
        self.frame_buffer = mp.Queue()
        self.finished = mp.Event()
        self.camTS = mp.Value('d',0)
        self.current_frame = mp.Array(ctypes.c_char_p,b'a')
        self.current_frame.value = b'a'
        self.stream_flag = mp.Value('b',True)
        self.startSave = mp.Value('b',False)
        self.startAcq = mp.Value('b',False)
        self.saving = mp.Value('b',False)
        self.flushing = mp.Value('b',False)
        self.triggerTime = mp.Value('d',0)
        self.piStreamDone = mp.Value('b',True)
        self.kill_flag = mp.Value('b',False)
        self.trialNum = 0
        self.iti_counter = 0
        self._last_interrupt_time = 0.0
        self.DEBOUNCE_SEC = 0.05

       
        #Initializing GPIO
        GPIO.setwarnings(False)
        GPIO.cleanup()  # clear any prior state
        GPIO.setmode(GPIO.BCM)
        
        # Inputs from Arduino:
        self.trial_pin = 25  # corresponds to Arduino → 7
        self.iti_pin = 24    # corresponds to Arduino → 8
        
        GPIO.setup(self.trial_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.iti_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        
        # Edge detection with modest debounce
        GPIO.add_event_detect(self.trial_pin, GPIO.BOTH, callback=self.interrupt_in, bouncetime=50)
        GPIO.add_event_detect(self.iti_pin, GPIO.BOTH, callback=self.iti_interrupt_in, bouncetime=50)
       
        #Initiate subprocesses to handle image acquisition
        self.saver = MovieSaver(fname=self.fname,startSave=self.startSave,saving=self.saving,frame_buffer=self.frame_buffer,flushing=self.flushing,piStreamDone=self.piStreamDone,kill_flag=self.kill_flag)
        self.output = ImgOutput(frame_buffer=self.frame_buffer,finished=self.finished,current_frame=self.current_frame,triggerTime=self.triggerTime,saving=self.saving,kill_flag=self.kill_flag)
        self.piStream = PiVideoStream(output=self.output,resolution=self.resolution,framerate=self.framerate,frame_buffer=self.frame_buffer,finished=self.finished,stream_flag=self.stream_flag,saving=self.saving,startAcq=self.startAcq,triggerTime=self.triggerTime,piStreamDone=self.piStreamDone,kill_flag=self.kill_flag)
      
        
    
    def _wait_for_saver_complete(self, timeout=0.5):
       deadline = time.time() + timeout
       while time.time() < deadline:
           if self.saver.saving_complete.value:
               return True
           time.sleep(0.005)
       print("Warning: previous save not finished before starting new segment")
       return False

    def _clear_frame_buffer(self):
       # Drain any leftover frames so new segment starts fresh
       while True:
           try:
               self.frame_buffer.get_nowait()
           except Empty:
               break
              
    def interrupt_in(self, channel):
       now = time.time()
       if now - self._last_interrupt_time < self.DEBOUNCE_SEC:
           return
       self._last_interrupt_time = now
   
       if GPIO.input(self.trial_pin):  # TRIAL START
           if not self._wait_for_saver_complete():
               print("Warning: starting trial before previous flush fully finished")
           self._clear_frame_buffer()
   
           self.triggerTime.value = time.perf_counter()
           self.trialNum += 1
           trial_str = str(self.trialNum)
           self.fname.value = self.fStub.value + 'cam_trial' + trial_str + '.data'
           self.startSave.value = True
           self.startAcq.value = True
           self.piStream.camera.annotate_text = ''
           print('Trial start interrupt detected by picam')
       else:  # TRIAL END → ITI START
           # end trial
           self.saving.value = False
           self.flushing.value = True
           self.piStream.camera.annotate_text = 'Not recording'
           print('Trial end interrupt detected by picam')
   
           # wait for trial to finish flushing
           if not self._wait_for_saver_complete():
               print("Proceeding to ITI despite incomplete trial flush")
           time.sleep(0.005)  # small intentional gap
           self._clear_frame_buffer()
   
           # start ITI
           self.iti_counter += 1
           iti_str = str(self.iti_counter)
           self.fname.value = self.fStub.value + 'cam_ITI' + iti_str + '.data'
           self.triggerTime.value = time.perf_counter()
           self.startSave.value = True
           self.startAcq.value = True
           self.piStream.camera.annotate_text = 'ITI ' + iti_str
           print('ITI start interrupt detected by picam')

    def iti_interrupt_in(self, channel):
        now = time.time()
        if now - self._last_interrupt_time < self.DEBOUNCE_SEC:
            return
        self._last_interrupt_time = now
   
        if GPIO.input(self.iti_pin):  # explicit ITI START
            self._wait_for_saver_complete()
            self._clear_frame_buffer()
   
            self.iti_counter += 1
            iti_str = str(self.iti_counter)
            self.fname.value = self.fStub.value + 'cam_ITI' + iti_str + '.data'
            self.triggerTime.value = time.perf_counter()
            self.startSave.value = True
            self.startAcq.value = True
            self.piStream.camera.annotate_text = 'ITI ' + iti_str
            print('ITI start interrupt detected by picam (via iti pin)')
        else:  # ITI END / session end
            self.saving.value = False
            self.flushing.value = True
            self.piStream.camera.annotate_text = 'Not recording'
            print('ITI end interrupt detected by picam')

    def reset_cam(self):
         self.stream_flag.value = True
         self.piStream.camera.annotate_background = picamera.Color('black')
         self.piStream.camera.annotate_text_size = 6
         self.piStream.camera.annotate_text = ''
       
    def endStream(self):
        self.stream_flag.value = False
        if self.saving.value:
            self.saving.value = False
           
    def read(self):
        # return the frame most recently produced to GUI
        if self.stream_flag.value and not self.current_frame.value==b'a':
            return self.current_frame.value
   
    def guiStartRecording(self):
        if not self.startSave.value:
            self.startSave.value = True
            self.startAcq.value = True
            self.fname.value = time.strftime("%Y%m%d") +  '_'+ time.strftime("%H%M%S") + 'rig.data'
            self.piStream.camera.annotate_text = ''
            self.triggerTime.value = time.perf_counter()
        else:
            print('Already saving to file')
       
    def guiStopRecording(self):
        if self.saving.value:
            self.saving.value = False
            self.flushing.value = True
            self.piStream.camera.annotate_text = 'Not recording'
        else:
            print('Stream is not currently saving')
           
    def passFstub(self,fStub):
        #Get fname when session starts
        self.fStub.value = fStub
        self.trialNum = 0
           
    def end(self):
        self.stream_flag.value = False
        self.kill_flag.value = True
        #print('got kill_flag')
        #Allow stream and saver to finish jobs
        while (not self.piStream.thread_complete.value) or (not self.saver.saving_complete.value):
            time.sleep(0.5)
            print('Waiting for camera threads to end')
            pass
        #Release resources
        self.piStream.camera.close()
        GPIO.cleanup()
