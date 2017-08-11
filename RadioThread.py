class RadioSendThread(threading.Thread):
    """ A thread to handle the primary radio """
	
    def __init__(self, threadID, radio, Q, exceptions, resetFlag, stopper):			# Constructor
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ser = radio
        self.sendQ = Q
        self.exceptionsQ = exceptions
        self.resetFlagQ = resetFlag
		self.stopper = stopper

    def run(self):
        try:
			while not self.stopper.is_set():
				while(not self.sendQ.empty()):              # If there are items in the sendQ, send them out the xbee
                    self.ser.write(self.sendQ.get())
                        
        ### Catches unexpected errors ###
        except Exception, e:
            self.exceptionsQ.put(str(e))
            self.resetFlagQ.put('gpsThread dead')
			
class RadioReceiveThread(threading.Thread):
    """ A thread to handle the primary radio """
	
    def __init__(self, threadID, radio, actionQ, xQ, exceptions, resetFlag, stopper):			# Constructor
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ser = radio
        self.actionQ = actionQ
		self.xQ = xQ
        self.exceptionsQ = exceptions
        self.resetFlagQ = resetFlag
		self.stopper = stopper

    def run(self):
        try:
			while not self.stopper.is_set():
				timeCheck = time.time()
                command = ''
                done = False
                while((not done) and (time.time() - timeCheck) < 3):
                    # Read from the RFD, if you fail to read, diabled the RFD and break the loop
                    try:
                        newChar = self.ser.read()
                    except:
                        self.rfdEnabled = False
                        done = True
                    # If the character is !, this is a command EOL character, so end the loop
                    if(newChar == "!"):
                        command += newChar
                        done = True
                    # If the character is anything else (not null), add it on, and reset the kill timer
                    elif(newChar != ""):
                        command += newChar
                        timeCheck = time.time()

                if(command != ''):
                    print("Command: ",command)
					
				if(command == 'IMAGE;1!'):
					self.actionQ.put('1')
					# self.mostRecentImage()
				elif(command == 'IMAGE;2!'):
					self.actionQ.put('2')
					# self.sendImageData()
				elif(command == 'IMAGE;3!'):
					self.actionQ.put('3')
					# self.requestedImage()
				elif(command == 'IMAGE;4!'):
					self.actionQ.put('4')
					# self.sendCameraSettings()
				elif(command == 'IMAGE;5!'):
					self.actionQ.put('5')
					# self.getCameraSettings()
				elif(command == 'IMAGE;6!'):
					self.actionQ.put('6')
					# self.pingTest()
				elif(command == 'IMAGE;7!'):
					self.actionQ.put('7')
					# self.sendPiRuntime()
				elif(command == 'IMAGE;8!'):
					self.actionQ.put('8')
					# self.timeSync()
				elif(command == 'IMAGE;9!'):
					self.actionQ.put('9')
					# self.horizontalFlip()
					# self.ser.reset_input_buffer()
				elif(command == 'IMAGE;0!'):
					self.actionQ.put('0')
					# self.verticalFlip()
					# self.ser.reset_input_buffer()
				elif(command == 'IMAGE;~!'):
					self.actionQ.put('~')
					# self.sendPing()
				elif(command == 'IMAGE;-!'):
					self.actionQ.put('-')
					# self.sendDeviceStatus()
					
	            # If it's not a command for the raspberry pi, send it out the xbee
                else:
					if(command != ''):
						self.xQ.put(command)      # Adds the command to the xbee send list so the xbee thread can send it out  

				self.ser.reset_input_buffer()       # Clear the input buffer so we're ready for a new command to be received
				
        ### Catches unexpected errors ###
        except Exception, e:
            self.exceptionsQ.put(str(e))
            self.resetFlagQ.put('gpsThread dead')