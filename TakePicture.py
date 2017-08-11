class TakePicture(threading.Thread):
    """ Thread to take two pictures, one at full resolution, the other at the selected resolution """
    def __init__(self, threadID, cameraSettings,folder,imagenumber,picQ):        # Constructor
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.cameraSettings = cameraSettings
        self.folder = folder
        self.imagenumber = imagenumber
        self.q = picQ

    def run(self):

        ### Open the camera ###
        try:
            camera = picamera.PiCamera()
        except:
            self.q.put('No Cam')        # If the camera fails to open, make sure the loop gets notified
            return
        
        try:
            settings = self.cameraSettings.getSettings()
            width = settings[0]
            height = settings[1]
            sharpness = settings[2]
            brightness = settings[3]
            contrast = settings[4]
            saturation = settings[5]
            iso = settings[6]
            # Setup the camera with the settings read previously
            camera.sharpness = sharpness
            camera.brightness = brightness
            camera.contrast = contrast
            camera.saturation = saturation
            camera.iso = iso
            camera.resolution = (2592,1944)             # Default max resolution photo
            extension = '.png'
            camera.hflip = self.cameraSettings.getHFlip()
            camera.vflip = self.cameraSettings.getVFlip()

            camera.capture(self.folder+"%s%04d%s" %("image",self.imagenumber,"_a"+extension))     # Take the higher resolution picture
            print "( 2592 , 1944 ) photo saved"

            fh = open(self.folder+"imagedata.txt","a")              # Save the pictures to imagedata.txt
            fh.write("%s%04d%s @ time(%s) settings(w=%d,h=%d,sh=%d,b=%d,c=%d,sa=%d,i=%d)\n" % ("image",self.imagenumber,"_a"+extension,str(datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")),2592,1944,sharpness,brightness,contrast,saturation,iso))       # Add it to imagedata.txt
            camera.resolution = (width,height)          # Switch the resolution to the one set by the ground station
            extension = '.jpg'

            camera.capture(self.folder+"%s%04d%s" %("image",self.imagenumber,"_b"+extension))     # Take the lower resolution picture
            print "(",width,",",height,") photo saved"
            fh.write("%s%04d%s @ time(%s) settings(w=%d,h=%d,sh=%d,b=%d,c=%d,sa=%d,i=%d)\n" % ("image",self.imagenumber,"_b"+extension,str(datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")),width,height,sharpness,brightness,contrast,saturation,iso))       # Add it to imagedata.txt
            print "settings file updated"
            self.q.put('done')
        except Exception, e:                                         # If there's any errors while taking the picture, reset the checkpoint
            print(str(e))
            self.q.put('checkpoint')

        finally:
            try:
                camera.close()
                fh.close()
            except:
                pass