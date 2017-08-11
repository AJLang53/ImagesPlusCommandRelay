class GPSThread(threading.Thread):
    """ A thread to read in raw GPS information, and organize it for the main thread """
    def __init__(self, threadID, gps, Q, exceptions, resetFlag,loggingGPS):			# Constructor
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.gpsSer = gps
        self.gpsQ = Q
        self.exceptionsQ = exceptions
        self.resetFlagQ = resetFlag
        self.loggingGPS = loggingGPS

    def run(self):
        global folder
        try:
            while True:					# Run forever
                line = self.gpsSer.readline()
                if(line.find("GPGGA") != -1):		# GPGGA indicates it's the GPS stuff we're looking for
                    try:
                        ### Parse the GPS Info ###
                        line = line.split(',')
                        if(line[1] == ''):
                            hours = 0
                            minutes = 0
                            seconds = 0
                        else:
                            hours = int(line[1][0:2])
                            minutes = int(line[1][2:4])
                            seconds = int(line[1][4:].split('.')[0])
                        if(line[2] == ''):
                            lat = 0
                        else:
                            lat = float(line[2][0:2]) + (float(line[2][2:]))/60
                        if(line[4] == ''):
                            lon = 0
                        else:
                            lon = -(float(line[4][0:3]) + (float(line[4][3:]))/60)
                        if(line[9] == ''):
                            alt = 0
                        else:
                            alt = float(line[9])
                        sat = int(line[7])
                        
                        ### Organize the GPS info, and put it in the queue ###
                        gpsStr = str(hours)+','+ str(minutes)+','+ str(seconds)+','+ str(lat)+','+str(lon)+','+str(alt)+','+str(sat)+'!'+'\n'
                        self.gpsQ.put(gpsStr)

                        if self.loggingGPS:
                            try:
                                f = open(folder+"gpslog.txt","a")
                                f.write(gpsStr)
                                f.close()
                            except Exception, e:
                                print("Error logging GPS")
                                self.exceptionsQ.put(str(e))
                
                    except Exception,e:
                        self.exceptionsQ.put(str(e))
                        
        ### Catches unexpected errors ###
        except Exception, e:
            self.exceptionsQ.put(str(e))
            self.resetFlagQ.put('gpsThread dead')