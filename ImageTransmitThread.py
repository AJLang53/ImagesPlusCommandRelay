class ImageTransmitThread(threading.Thread):    

	def __init__(self, threadID, radio, settingsQ, arg, recentimg, folder, cameraSetting, exceptions, resetFlag, stopper):			# Constructor
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ser = radio
        self.settingsQ = settingsQ
		self.arg = arg
		self.recentimg = recentimg
		self.folder = folder
		self.cameraSettings = cameraSettings
        self.exceptionsQ = exceptions
        self.resetFlagQ = resetFlag
		self.stopper = stopper

    def run(self):
	
        try:
			if self.arg == '1':
				self.mostRecentImage()
			elif self.arg == '2':
				self.sendImageData()
			elif self.arg == '3':
				self.requestedImage()
			elif self.arg == '4':
				self.sendCameraSettings()
			elif self.arg == '5':
				self.getCameraSettings()
			elif self.arg == '6':
				self.pingTest()
			elif self.arg == '7':
				self.sendPiRuntime()
			elif self.arg == '8':
				self.timeSync()
			elif self.arg == '~':
				self.sendPing()
			elif self.arg == '-':
				self.sendDeviceStatus()
			else:
				self.Q.put("Invalid Argument")
                        
        ### Catches unexpected errors ###
        except Exception, e:
            self.exceptionsQ.put(str(e))
            self.resetFlagQ.put('ImageTransmitThread dead')
	
	def image_to_b64(self,path):
        """ Converts an image to 64 bit encoding """
        with open(path,"rb") as imageFile:
            return base64.b64encode(imageFile.read())

    def b64_to_image(self,data,savepath):
        """ Converts a 64 bit encoding to an image """
        fl = open(savepath,"wb")
        fl.write(data.decode('base4'))
        fl.close()

    def gen_checksum(self,data,pos):
        """ Creates a checksum based on data """
        return hashlib.md5(data[pos:pos+self.wordlength]).hexdigest()

    def sendword(self,data,pos):
        """ Sends the appropriately sized piece of the total picture encoding """
        if(pos + self.wordlength < len(data)):       # Take a piece of size self.wordlength from the whole, and send it
            self.ser.write(data[pos:pos+self.wordlength])
            return
        else:                                   # If the self.wordlength is greater than the amount remaining, send everything left
            self.ser.write(data[pos:pos+len(data)])
            return

    def sync(self):
        """ Synchronizes the data stream between the Pi and the ground station """
        synccheck = ''
        synctry = 5
        syncterm = time.time() + 10
        while((synccheck != 'S')&(syncterm > time.time())):
            self.ser.write("sync")
            synccheck = self.ser.read()
            if(synctry == 0):
                if (synccheck == ""):
                    print "SyncError"
                    break
            synctry -= 1
        time.sleep(0.5)
        return

    def send_image(self,exportpath):
        """ Sends the image through the RFD in increments of size self.wordlength """
		
        timecheck = time.time()
        done = False
        cur = 0
        trycnt = 0
        outbound = self.image_to_b64(exportpath)     # Determine where the encoded image is
        size = len(outbound)
        print size,": Image Size"
        print "photo request received"
        self.ser.write(str(size)+'\n')               # Send the total size so the ground station knows how big it will be
        while(cur < len(outbound)):
            print "Send Position:", cur," // Remaining:", int((size - cur)/1024), "kB"      # Print out how much picture is remaining in kilobytes
            checkours = self.gen_checksum(outbound,cur)      # Create the checksum to send for the ground station to compare to
            self.ser.write(checkours)
            self.sendword(outbound,cur)                      # Send a piece of size self.wordlength
            checkOK = self.ser.read()
            if (checkOK == 'Y'):                # This is based on whether or not the word was successfully received based on the checksums
                cur = cur + self.wordlength
                trycnt = 0
            else:
                if(trycnt < 5):                 # There are 5 tries to get the word through, each time you fail, drop the self.wordlength by 1000
                    if self.wordlength >1000:
                        self.wordlength -= 1000
                    self.sync()
                    trycnt += 1
                    print "try number:", trycnt
                    print "resending last @", cur
                    print "ours:",checkours
                    print "self.wordlength",self.wordlength
                else:
                    print "error out"
                    cur = len(outbound)
        print "Image Send Complete"
        print "Send Time =", (time.time() - timecheck)
        return

    def mostRecentImage(self):
        """ Command 1: Send most recent image """
		
        self.ser.write('A')      # Send the acknowledge
        try:
            print "Send Image Command Received"
            print "Sending:", self.recentimg
            self.ser.write(self.recentimg)
            self.send_image(self.folder+self.recentimg)            # Send the most recent image
            self.wordlength = 7000                       # Reset the self.wordlength in case it was changed while sending
        except:
            print "Send Recent Image Error"

    def sendImageData(self):
        """ Command 2: Sends imagedata.txt """
		
        self.ser.write('A')
        try:
            print "data list request recieved"
            f = open(self.folder+"imagedata.txt","r")
            print "Sending imagedata.txt"
            for line in f:
                self.ser.write(line)
            self.ser.write('X\n')
            f.close()
            time.sleep(1)
        except:
            print "Error with imagedata.txt read or send"

    def requestedImage(self):
        """ Sends the requested image """
		
        self.ser.write('A')
        try:
            print"specific photo request recieved"
            temp = self.ser.readline()
            self.ser.reset_input_buffer()
            killTime = time.time() + 5
            while(temp.split(';')[0] != "RQ" and time.time() < killTime):
                temp = self.ser.readline()
##            while(temp != 'B' and time.time() < killTime):
##                temp = self.ser.readline()
            imagetosend = temp.split(';')[1]
##            imagetosend = self.ser.read(15)                  # Determine which picture to send
            self.send_image(self.folder+imagetosend)
            self.wordlength = 7000
        except Exception, e:
            print str(e)

    def sendCameraSettings(self):
        """ Sends the camera settings """
		
        self.ser.write('Ack\n')
        try:
            print "Attempting to send camera settings"
            settingsStr = self.cameraSettings.getSettingsString()
            self.ser.write(settingsStr+'\n')
            print "Camera Settings Sent"
            self.ser.reset_input_buffer()
        except Exception, e:
            print(str(e))

    def getCameraSettings(self):
        """ Updates the camera settings """
		
        self.ser.write('Ack1\n')
        try:
            print "Attempting to update camera settings"
            self.ser.reset_input_buffer()
            killTime = time.time() + 10
            self.ser.reset_input_buffer()
            
            temp = self.ser.readline()
            while(temp.split('/')[0] != "RQ" and time.time() < killTime):
                self.ser.write('Ack1\n')
                temp = self.ser.readline()
                
            if time.time() > killTime:
                return
            else:
                self.ser.write('Ack2\n')
                settings = temp.split('/')[1]
                settingsLst = settings.split(',')
                fail = False
                if len(settingsLst) == 7:
                    for each in settingsLst:
                        try:
                            each = each.replace('\n','')
                            each = int(each)
                        except:
                            fail = True
                            
                if fail == False:
                    self.cameraSettings.newSettings(settingsLst)
					self.settingsQ.put(self.cameraSettings)
                    print "Camera Settings Updated"
                    self.ser.write('Ack2\n')
                    self.ser.reset_input_buffer()
                    
        except Exception, e:
            print str(e)
            self.reset_cam()

    def timeSync(self):
        """ Sends the current time """
		
        self.ser.write('A')
        try:
            print "Time Sync Request Recieved"
            
            timeval=str(datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"))+"\n"     # Send the data time down to the ground station
            for x in timeval:
                self.ser.write(x)
        except:
            print "error with time sync"

    def pingTest(self):
        """ Connection test, test ping time """
		
        self.ser.write('A')
        print "Ping Request Received"
        try:
            termtime = time.time() + 10
            pingread = self.ser.read()
            while ((pingread != 'D') &(pingread != "") & (termtime > time.time())):     # Look for the stop character D, no new info, or too much time passing
                if (pingread == '~'):       # Whenever you get the P, send one back and get ready for another
                    print "Ping Received"
                    self.ser.reset_input_buffer()
                    self.ser.write('~')
                else:                       # If you don't get the P, sne back an A instead
                    print "pingread = ",pingread
                    self.ser.reset_input_buffer()
                    self.ser.write('A')
                pingread = self.ser.read()       # Read the next character
                sys.stdin.flush()
        except:
            print "Ping Runtime Error"

    def sendPing(self):
        """ Sends a Ping when requested """
		
        try:
            termtime = time.time() + 10
            pingread = self.ser.read()
            while ((pingread != 'D') &(pingread != "") & (termtime > time.time())):     # Look for the stop character D, no new info, or too much time passing
                if (pingread == '~'):       # Whenever you get the P, send one back and get ready for another
                    print "Ping Received"
                    self.ser.reset_input_buffer()
                    self.ser.write('~')
                else:                       # If you don't get the P, sne back an A instead
                    print "pingread = ",pingread
                    self.ser.reset_input_buffer()
                    self.ser.write('A')
                pingread = self.ser.read()       # Read the next character
                sys.stdin.flush()
        except:
            print "Ping Runtime Error"

    def sendPiRuntime(self):
        """ Sends the runtimedata """
		
        self.ser.write('A')
        try:
            print "Attempting to send piruntimedata"
            f = open(self.folder+"piruntimedata.txt","r")     # Open the runtimedata file
            temp = f.readline()
            while(temp != ""):      # Send everyting in the file until it's empty
                self.ser.write(temp)
                temp = f.readline()
            f.close()
            print "piruntimedata.txt sent"
        except:
            print "error sending piruntimedata.txt"

    def horizontalFlip(self):
        """ Flips the pictures horizontally """
		
        self.ser.write('A')
        try:
            self.cameraSettings.toggleHorizontalFlip()
			self.settingsQ.put(self.cameraSettings)
            print("Camera Flipped Horizontally")
        except:
            print("Error flipping image horizontally")

    def verticalFlip(self):
        """ Flips the pictures vertically """
		
        self.ser.write('A')
        try:
            self.cameraSettings.toggleVerticalFlip()
			self.settingsQ.put(self.cameraSettings)
            print("Camera Flipped Vertically")
        except:
            print("Error flipping image vertically")

    def sendDeviceStatus(self):
        """ Returns the status of the serial devices to the ground station """
		
        try:
            status = 'Camera: '+str(self.cameraEnabled)+', GPS: '+str(self.gpsEnabled)+', Xbee: '+str(self.xbeeEnabled) +', Temp: '+self.recentTemp + '\n'
            self.ser.write(status)
            print('Status Sent')
        except Exception, e:
            print(str(e))