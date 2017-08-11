class XbeeReceiveThread(threading.Thread):
    """ A thread to read information from the xbee, and send it to the main thread """
    def __init__(self,threadID, xbee, xbeeReceived, exceptions, resetFlag):         # Constructor
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.xbee = xbee
        self.receivedQ = xbeeReceived
        self.exceptionsQ = exceptions
        self.resetFlagQ = resetFlag

    def run(self):
        while self.xbee.isOpen():
            try:
                line = self.xbee.readline()         # Read a line from the xbee
                self.receivedQ.put(line)        # Put the information in the receivedQ
            except Exception, e:                    # Catch any unexpected error, and notify the main thread of them
                self.exceptionsQ.put(str(e))
                self.resetFlagQ.put('reset')


class XbeeSendThread(threading.Thread):
    """ A Thread to send information out through the xbee radio """
    def __init__(self,threadID, xbee, xbeeToSend,exceptions,resetFlag):         # Constructor
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.xbee = xbee
        self.sendQ = xbeeToSend
        self.exceptionsQ = exceptions
        self.resetFlagQ = resetFlag

    def run(self):
        while self.xbee.isOpen():
            try:
                while(not self.sendQ.empty()):              # If there are items in the sendQ, send them out the xbee
                    temp = self.sendQ.get()
                    self.xbee.write(str(self.sendQ.get()).encode())
                    
            except Exception, e:                            # Catch any unexpected error, and notify the main thread of them
                self.exceptionsQ.put(str(e))
                self.resetFlagQ.put('reset')