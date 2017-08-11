#!/usr/bin/env python
"""
Still Images and Command Relay for Raspberry Pi with Xbee and RFD 900+ 

Author:	Austin Langford, AEM, MnSGC
Based on work from the Montana Space Grant Consortium
Software created for use by the Minnesota Space Grant Consortium
Purpose: To communicate with a ground transceiver to receive commands, and relay them through the xbee
Additional Features: GPS beacon and Image Transmission
Creation Date: March 2016
"""

import time
import threading, Queue
from time import strftime
import datetime
import io
import picamera
import subprocess
import serial
import sys
import os
import base64
import hashlib
import serial.tools.list_ports

from GPSThread import *
from TempThread import *
from XbeeThreads import *
from TakePicture import *

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

temp_sensor = '/sys/bus/w1/devices/28-00000522ec61/w1_slave'

class Unbuffered:
    """ Helps eliminate the serial buffer, also logs all print statements to the logfile """
    def __init__(self,stream):
        self.stream = stream
    def write(self,data):
        self.stream.write(data)
        self.stream.flush()
        logfile.write(data)
        logfile.flush()

class CameraSettings:
    """ A class to handle camera settings """
    def __init__(self,width,height,sharpness,brightness,contrast,saturation,iso):
        self.width = width
        self.height = height
        self.resolution = (width,height)
        self.sharpness = sharpness
        self.brightness = brightness
        self.contrast = contrast
        self.saturation = saturation
        self.iso = iso
        self.hflip = False
        self.vflip = False

    def getSettings(self):
        return [self.width, self.height, self.sharpness, self.brightness, self.contrast, self.saturation ,self.iso]

    def getSettingsString(self):
        return str(self.width) + ',' + str(self.height) + ',' + str(self.sharpness) + ',' + str(self.brightness) + ',' + str(self.contrast) + ',' + str(self.saturation) + ',' + str(self.iso)
    
    def setCameraAnnotation(self,annotation):
        self.annotation = annotation

    def getCameraAnnotation(self):
        return self.annotation

    def getHFlip(self):
        return self.hflip

    def getVFlip(self):
        return self.vflip

    def toggleHorizontalFlip(self):
        if(self.hflip == False):
                self.hflip = True
        else:
                self.hflip = False
        return self.hflip

    def toggleVerticalFlip(self):
        if(self.vflip == False):
                self.vflip = True
        else:
                self.vflip = False
        return self.vflip

    def newSettings(self,settings):
        self.width = int(settings[0])
        self.height = int(settings[1])
        self.sharpness = int(settings[2])
        self.brightness = int(settings[3])
        self.contrast = int(settings[4])
        self.saturation = int(settings[5])
        self.iso = int(settings[6])
        self.resolution = (self.width,self.height)

class main:
        
    """ The main program class """
    def __init__(self, folder, loggingGPS, loggingTemp):
        self.folder = folder
		self.loggingGPS = loggingGPS
		self.loggingTemp = loggingTemp

        # Get a list of the usb devices connected and assign them properly
        ports = serial.tools.list_ports.comports()
        serialConverters = []
        for each in ports:
            print(each.vid,each.pid,each.hwid)
            if each.vid == 1027 and each.pid == 24597:
                self.xPort = each.device
                print('Xbee on ' + str(each.device))
            elif each.vid == 1659 and each.pid == 8963:
                serialConverters.append(each)

        # The USB-serial converters don't have unique IDs, so they need to be checked
        for each in serialConverters:
            gpsTest = serial.Serial(port = each.device, baudrate = 9600, timeout = 1)
            try:
                sample = gpsTest.readline()
                print(sample)
                sample = gpsTest.readline()     # Get 2 lines to make sure it's a full line
                print(sample)
                print(sample[0:2])
                if sample[0:2] == "$G":
                    self.gpsPort = each.device
                    print('GPS on ' + str(each.device))
                else:
                    self.rfdPort = each.device
                    print('RFD on ' + str(each.device))
            except Exception, e:
                print(str(e))

        ### Serial Port Initializations ###
        #RFD900 Serial Variables
        self.rfdBaud = 38400
        self.rfdTimeout = 3

        # GPS Serial Variables
        self.gpsBaud = 9600
        self.gpsTimeout = 3

        # XBee Serial Variables
        self.xBaud = 9600
        self.xTimeout = 3

        # Create the imagedata.txt file
        fh = open(self.folder + "imagedata.txt","w")
        fh.write("")
        fh.close()

        ### Picture Variables ###
        self.wordlength = 7000
        self.imagenumber = 0
        self.recentimg = ""
        self.pic_interval = 60
        self.cameraSettings = CameraSettings(150,100,0,50,0,0,400)
        self.reset_cam()
        self.takingPicture = False
		
        ### Create queues to share info with the threads
		self.actionQ = Queue.Queue()
		self.sendQ = Queue.Queue()
        self.xSendQ = Queue.Queue()
        self.xReceivedQ = Queue.Queue()
        self.xReceivedExceptionsQ = Queue.Queue()
        self.xSendExceptionsQ = Queue.Queue()
        self.xReceivedResetQ = Queue.Queue()
        self.xSendResetQ = Queue.Queue()
        self.gpsQ = Queue.LifoQueue()
        self.gpsExceptionsQ = Queue.Queue()
        self.gpsResetQ = Queue.Queue()
        self.tempQ = Queue.LifoQueue()
        self.tempExceptionsQ = Queue.Queue()
        self.tempResetQ = Queue.Queue()
        self.picQ = Queue.Queue()

        ### Try to create the various serial objects; if they fail to be created, set them as disabled ###
        # RFD 900
        try:
            self.ser = serial.Serial(port = self.rfdPort,baudrate = self.rfdBaud, timeout = self.rfdTimeout)
            self.rfdEnabled = True
        except:
            self.rfdEnabled = False
            print('RFD disabled')

        # Camera
        try:
            camera = picamera.PiCamera()
            camera.close()
            self.cameraEnabled = True
        except:
            self.cameraEnabled = False
            if(self.rfdEnabled):
                self.ser.write('Alert: Camera is disabled\n')
            print('Camera disabled')
            
        # Xbee
        try:
            self.xbee = serial.Serial(port = self.xPort, baudrate = self.xBaud, timeout = self.xTimeout)
            self.xbeeEnabled = True
        except:
            self.xbeeEnabled = False
            if(self.rfdEnabled):
                self.ser.write('Alert: Xbee is disabled\n')
            print('Xbee disabled')
            
        # GPS
        try:
            self.gps = serial.Serial(port = self.gpsPort, baudrate = self.gpsBaud, timeout = 1)
            self.gpsEnabled = True
        except:
            self.gpsEnabled = False
            if(self.rfdEnabled):
                self.ser.write('Alert: GPS is disabled\n')
            print('GPS disabled')

        # Temp Sensor
        try:
            f = open(temp_sensor,'r')
            lines = f.readlines()
            f.close()
            if(lines[0].strip()[-3:] != 'YES'):
                self.tempEnabled = False
                if(self.rfdEnabled):
                    self.ser.write('Alert: Temp Sensor is disabled\n')
                print('Temp Sensor Disabled')
            else:
                self.tempEnabled = True
                
        except Exception, e:
            print(str(e))
            self.tempEnabled = False
            if(self.rfdEnabled):
                self.ser.write('Alert: Temp Sensor is disabled\n')
            print('Temp Sensor Disabled')
                
        ### Start the appropriate side threads ###
        # Xbee
        if(self.xbeeEnabled):
            self.startXbeeThreads()

        # GPS
        if(self.gpsEnabled):
            self.startGPSThread()

        # Temp Sensor
        if(self.tempEnabled):
            self.startTempThread()

        # Get Started
        self.starttime = time.time()
        print "Started at @ ",datetime.datetime.now()
        self.checkpoint = time.time()


    def getGPSCom(self):
        return [self.gpsPort,self.gpsBaud,self.gpsTimeout]

    def getXbeeCom(self):
        return [self.xPort,self.xBaud,self.xTimeout]

    def getRFDCom(self):
        return [self.rfdPort,self.rfdBaud,self.rfdTimeout]

    def reset_cam(self):
        """ Resets the camera to the default settings """
        self.cameraSettings = CameraSettings(150,100,0,50,0,0,400)

	def startRadioThreads(self):
		# Radio Receive Thread
		self.radioReceiveThread = RadioReceiveThread("radioReceiveThread",self.ser, self.actionQ, self.radioReceiveExceptionsQ, self.radioReceiveResetQ, self.radioReceiveStopper)
		self.radioReceiveThread.daemon = True
		self.radioReceiveThread.start()
		
		# Radio Send Thread
		self.radioSendThread = RadioSendThread("radioSendThread", self.ser, self.sendQ, self.radioSendExcetptionsQ, self.radioSendResetQ, self.radioSendStopper)
		self.radioSendThread.daemon = True
		self.radioSendThread.start()
			
    def startXbeeThreads(self):
        # Xbee Receive Thread
        self.xReceiveThread = XbeeReceiveThread("xbeeReceivedThread",self.xbee, self.xReceivedQ, self.xReceivedExceptionsQ, self.xReceivedResetQ)
        self.xReceiveThread.daemon = True
        self.xReceiveThread.start()

        # Xbee Send Thread
        self.xSendThread = XbeeSendThread("xbeeSendThread", self.xbee, self.xSendQ, self.xSendExceptionsQ, self.xSendResetQ)
        self.xSendThread.daemon = True
        self.xSendThread.start()

    def startGPSThread(self):
        self.gpsThread = GPSThread("gpsThread",self.gps, self.gpsQ, self.gpsExceptionsQ, self.gpsResetQ, self.loggingGPS)
        self.gpsThread.daemon = True
        self.gpsThread.start()

    def startTempThread(self):
        self.tempThread = TempThread("tempThread", self.tempQ, self.tempExceptionsQ, self.tempResetQ, self.loggingTemp)
        self.tempThread.daemon = True
        self.tempThread.start()

    def checkSideThreads(self):
        """ Check to make sure the side threads are still running """
        # If either of the xbee threads need to be reset, reset them both, and recreate the xbee object just to make sure that the xbee wasn't the issue
        if(self.xbeeEnabled):
            if((not self.xReceivedResetQ.empty()) or (not self.xSendResetQ.empty())):
                try:
                    self.xbee.close()       # Try to close the xbee
                    print('xbee closed')
                except:
                    pass

                try:
                    self.xbee = serial.Serial(port = self.xPort, baudrate = self.xBaud, timeout = self.xTimeout)        # Reopen the xbee
                    self.xbee.close()
                    self.xbee.open()
                    print(self.xbee.isOpen())
                    self.startXbeeThreads()     # Restart the threads

                    # Empty the reset Qs
                    while(not self.xReceivedResetQ.empty()):
                        self.xReceivedResetQ.get()
                    while(not self.xSendResetQ.empty()):
                        self.xSendResetQ.get()
                except Exception, e:
                    print(str(e))
                    self.xbeeEnabled = False        # If this fails, disable the xbee
                    if(self.rfdEnabled):
                        self.ser.write("Alert: Xbee is now disabled")
                    print("Xbee is now Disabled")

        # If the gps thread needs to be reset, do it
        if(self.gpsEnabled):
            if(not self.gpsResetQ.empty()):
                try:
                    self.gps.close()       # Try to close the gps
                except:
                    pass

                try:
                    self.gps = serial.Serial(port = self.gpsPort, baudrate = self.gpsBaud, timeout = self.gpsTimeout)       # Reopen the GPS
                    self.startGPSThread()       # Restart the thread
                    print('here')
                    # Clear the gps reset Q
                    while(not self.gpsResetQ.empty()):
                        self.gpsResetQ.get()
                except:
                    self.gpsEnabled = False     # If this fails, disable the gps
                    if(self.rfdEnabled):
                        self.ser.write('Alert: GPS is disabled')
                    print("GPS is now Disabled")

        if(self.tempEnabled):
            if(not self.tempResetQ.empty()):
                try:
                    f = open(temp_sensor,'r')
                    lines = f.readlines()
                    f.close()
                    if(lines[0].strip()[-3:] != 'YES'):
                        self.tempEnabled = False     # If this fails, disable the gps
                        if(self.rfdEnabled):
                            self.ser.write('Alert: Temp Sensor is disabled')
                        print("Temp Sensor is Disabled")
                    else:
                        self.tempEnabled = True
                        self.tempResetQ.put('reset')
                        if(self.rfdEnabled):
                            self.ser.write('Temp Sensor is now Enabled')
                        print("Temp Sensor Enabled")
                        self.startTempThread()       # Restart the thread
                        # Clear the temp reset Q
                        while(not self.tempResetQ.empty()):
                            self.tempResetQ.get()
                except:
                    self.tempEnabled = False     # If this fails, disable the gps
                    if(self.rfdEnabled):
                        self.ser.write('Alert: Temp Sensor is disabled')
                    print("Temp Sensor is Disabled")

    def loop(self):
        """ The main loop for the program """
        try:    
			if not self.actionQ.empty():
				self.radioStopper
				self.transmitImage = ImageTransmitThread("Image Transmitter", self.ser, settingsQ, self.actionQ.get(), self.recentimg, self.folder, self.cameraSettings, self.imageTransmitExceptionQ, self.imageTransmitResetQ, self.imageTransmitStopper)
				self.transmitImage.daemon = True
				self.transmitImage.start()
				self.transmittingImage = True
				while not self.actionQ.empty():
					self.actionQ.get()
				
			### Send information to the ground station ###
			# Send a GPS update through the RFD
			if(self.gpsEnabled):
				if(not self.gpsQ.empty()):
					gps = "GPS:" + str(self.gpsQ.get())
					self.sendQ.put(gps)
					while(not self.gpsQ.empty()):
						self.gpsQ.get()

			# Temperature
			if(self.tempEnabled):
				if(not self.tempQ.empty()):
					self.recentTemp = str(self.tempQ.get())
					print("Temperature: "+self.recentTemp)
					while(not self.tempQ.empty()):
						self.tempQ.get()
			else:
				self.recentTemp = "False"

			# Send out everything the xbee received
			if(self.xbeeEnabled):
				while(not self.xReceivedQ.empty()):
					self.sendQ.put(self.xReceivedQ.get())
                        
            self.checkSideThreads()             # Make sure the side threads are still going strong

            ### Periodically take a picture ###
            if(self.cameraEnabled):
                if(self.checkpoint < time.time() and not self.takingPicture):			# Take a picture periodically
                    try:
                        camera = picamera.PiCamera()
                        camera.close()
                    except:
                        self.cameraEnabled = False
                        if(self.rfdEnabled):
                            self.sendQ.put('Alert: Camera is disabled\n')
                        print('Camera disabled')
                    if self.cameraEnabled:
                        print("Taking Picture")
                        self.takingPicture = True
                        self.picThread = TakePicture("Picture Thread",self.cameraSettings, self.folder,self.imagenumber,self.picQ)
                        self.picThread.daemon = True
                        self.picThread.start()
                
            ### Check for picture stuff ###
            if(self.cameraEnabled):
                if(not self.picQ.empty()):
                    if(self.picQ.get() == 'done'):                      # Command to reset the recentimg and increment the pic number (pic successfully taken)
                        self.recentimg = "%s%04d%s" %("image",self.imagenumber,"_b.jpg")
                        self.imagenumber += 1
                        self.takingPicture = False
                        self.checkpoint = time.time() + self.pic_interval
                    elif(self.picQ.get() == 'reset'):                   # Command to reset the camera
                        self.takingPicture = False
                        self.reset_cam()
                    elif(self.picQ.get() == 'checkpoint'):              # Command to reset the checkpoint
                        self.takingPicture = False
                        self.checkpoint = time.time() + self.pic_interval
                    elif(self.picQ.get() == 'No Cam'):                  # Command to disable the camera
                        self.cameraEnabled = False
                    else:
                        while(not self.picQ.empty()):                   # Clear the queue of any unexpected messages
                            print(self.picQ.get())
            
            ### Print out any exceptions that the threads have experienced ###
            if(self.gpsEnabled):
                while(not self.gpsExceptionsQ.empty()):
                    print(self.gpsExceptionsQ.get())
            if(self.xbeeEnabled):
                while(not self.xReceivedExceptionsQ.empty()):
                    print(self.xReceivedExceptionsQ.get())
                while(not self.xSendExceptionsQ.empty()):
                    print(self.xSendExceptionsQ.get())
            if(self.tempEnabled):
                while(not self.tempExceptionsQ.empty()):
                    print(self.tempExceptionsQ.get())

            ### Check if there is now an Xbee, GPS, RFD, or Camera attached; if there is, get it going

            # Camera Check
            if(not self.cameraEnabled):
                try:
                    camera = picamera.PiCamera()
                    camera.close()
                    self.cameraEnabled = True
                    print('Camera is now Enabled')
                    if(self.rfdEnabled):
                        self.sendQ.put('Camera is now Enabled')
                except:
                    pass

            # Temp Sensor Check
            if(not self.tempEnabled):
                try:
                    f = open(temp_sensor,'r')
                    lines = f.readlines()
                    f.close()
                    if(lines[0].strip()[-3:] != 'YES'):
                        pass
                    else:
                        self.tempEnabled = True
                        self.tempResetQ.put('reset')
                        if(self.rfdEnabled):
                            self.sendQ.put('Temp Sensor is now Enabled')
                        print("Temp Sensor Enabled")
                        
                except Exception, e:
                    pass

            # Xbee Check
            if (not self.xbeeEnabled):
                ports = serial.tools.list_ports.comports()
                for each in ports:
                    if each.vid == 1027 and each.pid == 24597:      # The vid and pid for the xbee, start it up if they match one of the comports
                        if(not self.xbeeEnabled):
                            self.xPort = each.device
                            try:
                                self.xbee = serial.Serial(port = self.xPort, baudrate = self.xBaud, timeout = self.xTimeout)
                                self.xbeeEnabled = True
                                self.xSendResetQ.put('reset')
                                self.xReceivedResetQ.put('reset')        # This will cause the threads to be restarted in the the checkSideThreads call next loop
                                self.xbee.close()                       # Close the xbee so it can be opened again later
                                print('Xbee is now Enabled')
                                if(self.rfdEnabled):
                                    self.ser.write('Xbee is now Enabled')
                            except Exception, e:
                                pass

            # RFD and GPS Check           
            if (not self.gpsEnabled) or (not self.rfdEnabled):
                ports = serial.tools.list_ports.comports()
                for each in ports:
                    if each.vid == 1659 and each.pid == 8963:
                        if each.device != self.rfdPort:
                            gpsTest = serial.Serial(port = each.device, baudrate = 9600, timeout = 1)
                            try:
                                sample = gpsTest.readline()
                                sample = gpsTest.readline()     # Get 2 lines to make sure it's a full line
                                if sample[0:2] == "$G":
                                    self.gpsPort = each.device
                                    self.gps = serial.Serial(port = self.gpsPort, baudrate = self.gpsBaud, timeout = self.gpsTimeout)
                                    self.gpsEnabled = True
                                    self.gpsResetQ.put('reset')             # This will cause the thread to be restarted in the the checkSideThreads call next loop
                                    self.gps.close()                        # Close the GPS so it can be opened again later
                                    print('GPS is now Enabled')
                                    if(self.rfdEnabled):
                                        self.ser.write('GPS is now Enabled')
                                else:
                                    if (not self.rfdEnabled):
                                        self.rfdPort = each.device
                                        print('RFD is now Enabled')
                            except Exception, e:
                                print(str(e))

        except KeyboardInterrupt:       # For debugging pruposes, close the RFD port and quit if you get a keyboard interrupt
            self.ser.close()
            quit()
            			
        except Exception, e:            # Print any exceptions from the main loop
            print(str(e))

if __name__ == "__main__":
    ### Check for, and create the folder for this flight ###
    folder = "/home/pi/RFD_Pi_Code/%s/" % strftime("%m%d%Y_%H%M%S")
    dir = os.path.dirname(folder)
    if(not os.path.exists(dir)):
        os.mkdir(dir)

    ### Create the logfile ###
    try:
        logfile = open(folder+"piruntimedata.txt","w")
        logfile.close()
        logfile = open(folder+"piruntimedata.txt","a")
        loggingRuntime = True
    except:
        loggingRuntime = False
        print("Failed to create piruntimedata.txt")

    sys.stdout = Unbuffered(sys.stdout)         # All print statements are written to the logfile

    try:
        gpsLog = open(folder+"gpslog.txt","a")
        gpsLog.close()
        loggingGPS = True
    except:
        loggingGPS = False
        print("Failed to create gpslog.txt")
        
    try:
        tempLog = open(folder+"templog.txt","a")
        tempLog.close()
        loggingTemp = True
    except:
        loggingTemp = False
        print("Failed to create templog.txt")
        
    mainLoop = main(folder, loggingGPS, loggingTemp)
    while True:
        mainLoop.loop()

