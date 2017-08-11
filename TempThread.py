class TempThread(threading.Thread):
    """ A thread to read in raw temperature sensor information, and organize it for the main thread """
    def __init__(self, threadID, Q, exceptions, resetFlag, loggingTemp):			# Constructor
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.tempQ = Q
        self.exceptionsQ = exceptions
        self.resetFlagQ = resetFlag
        self.loggingTemp = loggingTemp

    def temp_raw(self):
        f = open(temp_sensor,'r')
        lines = f.readlines()
        f.close()
        return lines

    def read_temp(self):
        lines = self.temp_raw()
        temp_output = lines[1].find('t=')
        if temp_output != 1:
            temp_string = lines[1].strip()[temp_output+2:]
            temp_c = float(temp_string)/1000.0
            temp_f = temp_c*9.0/5.0 + 32.0
            return temp_c, temp_f
        
    def run(self):
        global folder
        try:
            while True:					# Run forever
                temp = self.read_temp()
                self.tempQ.put(temp)

                if self.loggingTemp:
                    try:
                        curTime = str(datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"))
                        f = open(folder+"templog.txt","a")
                        f.write(curTime+" - "+str(temp)+"\n")
                        f.close()
                    except Exception, e:
                        print(str(e))
                        self.exceptionsQ.put(str(e))
                        
        ### Catches unexpected errors ###
        except Exception, e:
            self.exceptionsQ.put(str(e))
            self.resetFlagQ.put('tempThread dead')