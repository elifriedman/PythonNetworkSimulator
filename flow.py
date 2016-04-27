import simpy
import random
from numpy import inf

from link import *
from node import *


SS = 1 # slow start
CA = 2 # congestion avoidance
FR = 3 # fast recovery
def state2str(state):
  if state==1:
    return "SS"
  if state==2:
    return "CA"
  if state==3:
    return "FR"
  return "-"

class Flow:
  def __init__(self,name, src, dest, KBamount, start, tcptype, env):
    self.name = name
    self.src = src
    self.srcdata = simpy.Store(env)
    self.dest = dest
    self.destdata = simpy.Store(env)
    self.data = KBamount*1024 # bytes
    self.start = start
    self.tcptype = tcptype.lower()
    if self.tcptype!='tahoe' and self.tcptype!='reno':
      raise Exception("TCP Type must either be 'tahoe' or 'reno'!")
    self.env = env
    self.actionSrc = env.process(self.runSrc())
    self.actionDest = env.process(self.runDest())

    # TCP variables
    self.cwnd = 1.0
    self.cwndinc = 1.0
    self.ssthresh = 180
    self.ackCounter = 0
    self.state = SS
    self.sentpackets = []
    self.rttracker = [0,0]
    self.estRTT = 0.08
    self.devRTT = 0.0001

    # measurement variables
    self.nextMeas = 1.0
    self.lastMeas = 0.0
    self.dataSent = 0.0
    self.flowrate = 0.0

  def timeoutInterval(self):
    return self.estRTT + 4*self.devRTT+1E-6

  def dataDelivery(self,packet,delivering_node):
    if delivering_node == self.src:
      self.srcdata.put(packet)
    elif delivering_node == self.dest:
      self.destdata.put(packet)

  def runSrc(self):
    """ Runs all the logic for the source node of the flow.
    This function waits until the user specified for this flow to start and
    then loops until we have no more data, creating events, sending data to
    the destination, and receiving acks from the destination. This function
    can run two versions of TCP--Tahoe and Reno.
    """
    yield self.env.timeout(self.start)
    self.lastMeas = self.env.now
    self.nextMeas = self.env.now + 1.0

    pktsize = 1024
    seqnum = 0
    while self.data > 0:
      # send as many packets as cwnd will let us
      for i in range(int(self.cwnd-len(self.sentpackets))):
        size = pktsize
        if self.data < pktsize:
          size = self.data
        packet = Packet(size,self,loginfo=[self.env.now])
        packet.setHeader(src=self.src.name,
                         dest=self.dest.name,
                         seq=seqnum)
        self.sentpackets.append(packet)
        seqnum += 1
        self.data -= len(packet)
        self.dataSent += len(packet)
        self.src.links[0].sendData(packet,self.src)

      def timeoutfn():
        """ Create a timeout event, but only interrupt if the packet
            wasn't acked.
        """
        pkt = self.sentpackets[0]
        timeout = self.env.timeout(self.timeoutInterval())
        yield timeout
        if pkt in self.sentpackets:
          self.actionSrc.interrupt()
      self.env.process(timeoutfn())
      try:
        ackpkt = yield self.srcdata.get() # wait for a packet to arrive

        firstack = False
        # remove packets from list, since they were acked
        while len(self.sentpackets) > 0 and \
              ackpkt.getAckNum() >= self.sentpackets[0].getSeqNum():
          firstack = True
          self.sentpackets.pop(0)

        if firstack: # update timeout interval
          timethere = ackpkt.loginfo[0]
          timeback = self.env.now - ackpkt.loginfo[1]
          sampleRTT = timethere+timeback
          self.estRTT = 0.875*self.estRTT + 0.125*sampleRTT
          self.devRTT = 0.75*self.devRTT + 0.25*abs(sampleRTT-self.estRTT)

        dupack = False
        # if the destination is expecting the next packet (i.e. it's a dupAck)
        if len(self.sentpackets) > 0 and \
              ackpkt.getAckNum()+1 == self.sentpackets[0].getSeqNum():
          dupack = True

        # state machine for TCP Tahoe and Reno
        if self.state == SS or self.state == CA:
          if self.state == SS: cwndinc = 1.0
          elif self.state == CA: cwndinc = 15.5 / self.cwnd
          if firstack:
            self.ackCounter = 0
            self.cwnd += cwndinc
          elif dupack:
            self.ackCounter += 1
          if self.cwnd >= self.ssthresh: # SS -> CA
            self.state = CA
          if self.ackCounter > 3:
            print "TRIPACK,%f,%s,%d" % (self.env.now,self.name,ackpkt.getAckNum())
            self.ssthresh = self.cwnd/2
            if self.tcptype == 'tahoe':
              self.cwnd = 1
              self.state = SS
            elif self.tcptype == 'reno': # SS -> FR
              self.cwnd = self.ssthresh+3
              self.state = FR
            if len(self.sentpackets) > 0:
              self.sentpackets[0].loginfo[0] = self.env.now
              self.src.links[0].sendData(self.sentpackets[0],self.src)
        elif self.state == FR:
          if firstack:
            self.cwnd = self.ssthresh
            self.ackCounter = 0
            self.state = CA
          elif dupack:
            self.cwnd += 1.0
            # don't retransmit?
        if self.env.now > self.nextMeas:
          time = self.env.now - self.lastMeas
          self.flowrate = self.dataSent / time
          self.dataSent = 0.0
          self.lastMeas = self.env.now
          self.nextMeas = self.env.now + 1.0

        print "FLOW,%f,%s,%d,%d,%f,%f,%s" % (self.env.now,self.name,
                                             self.cwnd,self.data,
                                             self.estRTT,self.flowrate,
                                             state2str(self.state))

      except simpy.Interrupt: # TIMEOUT!
        print "TIME,%f,%s,%d" % (self.env.now,self.name,self.sentpackets[0].getSeqNum())
        self.ssthresh = self.cwnd/2
        self.cwnd = 1
        self.ackCounter = 0
        self.state = SS
        if len(self.sentpackets) > 0:
          self.sentpackets[0].loginfo[0] = self.env.now
          self.src.links[0].sendData(self.sentpackets[0],self.src)
        self.srcdata = simpy.Store(self.env)

  def runDest(self):
    seqnum = random.randint(0,100)
    self.nextAck = -1
    self.unacked = []
    while True:
      packet = yield self.destdata.get()
#      print "%f: Received %d,%d" % (self.env.now,packet.getSeqNum(),self.nextAck)
      resp = Packet(64,self,loginfo=[self.env.now-packet.loginfo[0]])
      if self.nextAck == -1:
        self.nextAck = packet.getSeqNum()
      # if a packet arrived out of order
      if self.nextAck < packet.getSeqNum():
        futurepkt = Packet(64,self,loginfo=[self.env.now-packet.loginfo[0]])
        futurepkt.setHeader(src=self.dest.name,
                           dest=self.src.name,
                           seq=-1,
                           ack=packet.getSeqNum())
        self.unacked.append(futurepkt)

        resp.setHeader(src=self.dest.name, dest=self.src.name,
                       seq=seqnum, ack=self.nextAck-1) # send dupack
        resp.loginfo.append(self.env.now)
        self.dest.links[0].sendData(resp,self.dest)

      # if we were expecting this packet
      elif self.nextAck == packet.getSeqNum():
        resp.setHeader(src=self.dest.name, dest=self.src.name,
                      seq=seqnum, ack=packet.getSeqNum())
        self.unacked.append(resp)
        self.unacked.sort(key=lambda pkt: pkt.getAckNum())

        # only ack the latest packet we receiced
        while len(self.unacked)>0 and self.nextAck == self.unacked[0].getAckNum():
          resp = self.unacked.pop(0)
          self.nextAck = resp.getAckNum()+1

        resp.loginfo.append(self.env.now) # store RTT info in packet to make life easier
        self.dest.links[0].sendData(resp,self.dest)
