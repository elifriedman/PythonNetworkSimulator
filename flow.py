import simpy
import random
from numpy import inf

from link import *
from node import *


class Flow:
  def __init__(self,name, src, dest, KBamount, start,tcptype='tahoe',env):
    self.name = name
    self.src = src
    self.srcdata = simpy.Store(env)
    self.dest = dest
    self.destdata = simpy.Store(env)
    self.data = KBamount*1024 # bytes
    self.start = start
    self.type = 'tahoe'
    self.env = env
    self.actionSrc = env.process(self.runSrc())
    self.actionDest = env.process(self.runDest())

    # TCP variables
    self.cwnd = 1.0
    self.cwndinc = 1.0
    self.ssthresh = 180
    self.ackCounter = 0
    self.sentpackets = []
    self.rttracker = [0,0]
    self.estRTT = 0.08
    self.devRTT = 0.0001

  def timeoutInterval(self):
    return self.estRTT + 4*self.devRTT+1E-6

  def dataDelivery(self,packet,delivering_node):
    if delivering_node == self.src:
      self.srcdata.put(packet)
    elif delivering_node == self.dest:
      self.destdata.put(packet)

  def runSrc(self):
    yield self.env.timeout(self.start)
#    print "%s started at %f" % (self.name,self.env.now)
    pktsize = 1024
    seqnum = 0; random.randint(0,100)
    self.rttracker[0] = seqnum
    self.rttracker[1] = self.env.now
    while self.data > 0:

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
        ackpkt = yield self.srcdata.get()

#        sampleRTT = self.env.now-self.rttracker[1]
#        self.estRTT = 0.875*self.estRTT + 0.125*sampleRTT
#        self.devRTT = 0.75*self.devRTT + 0.25*abs(sampleRTT-self.estRTT)

        # remov packets from list, since they were acked
        while len(self.sentpackets) > 0 and \
              ackpkt.getAckNum() >= self.sentpackets[0].getSeqNum():
          self.ackCounter = 0
          self.sentpackets.pop(0)

        # if the destination is expecting the next packet (i.e. it's a dupAck)
        if len(self.sentpackets) > 0 and \
              ackpkt.getAckNum()+1 == self.sentpackets[0].getSeqNum():
          self.ackCounter += 1
        print "CWND,%f,%s,%d" % (self.env.now,self.name, self.cwnd)

        # triple dupAck
        if self.ackCounter == 4:
          self.ackCounter = 0
          self.ssthresh = self.cwnd / 2
          self.cwnd = 0
          pkt = self.sentpackets[0]
          self.rttracker[0] = -1
          self.src.links[0].sendData(pkt,self.src)

        if self.cwnd >= self.ssthresh:
          self.cwndinc = 15.5/self.cwnd
        else:
          self.cwndinc = 1.0

        self.cwnd += self.cwndinc
      except simpy.Interrupt: # TIMEOUT!
        self.ackCounter = 0
        self.cwnd = 1
        if len(self.sentpackets) > 0:
          pkt = self.sentpackets[0]
          self.rttracker[0] = -1
#          print "%f: Timeout. Sent %d" % (self.env.now,pkt.getSeqNum())
          self.src.links[0].sendData(pkt,self.src)
        self.srcdata = simpy.Store(self.env)

  def runDest(self):
    seqnum = random.randint(0,100)
    self.nextAck = -1
    self.unacked = []
    while True:
      packet = yield self.destdata.get()
#      print "%f: Received %d,%d" % (self.env.now,packet.getSeqNum(),self.nextAck)
      resp = Packet(64,self,loginfo=packet.loginfo)
      if self.nextAck == -1:
        self.nextAck = packet.getSeqNum()
      if self.nextAck < packet.getSeqNum():
        futurepkt = Packet(64,self,loginfo=packet.loginfo)
        futurepkt.setHeader(src=self.dest.name,
                           dest=self.src.name,
                           seq=-1,
                           ack=packet.getSeqNum())
        self.unacked.append(futurepkt)

        resp.setHeader(src=self.dest.name, dest=self.src.name,
                       seq=seqnum, ack=self.nextAck-1)
#        print "%f: Responding with %d" % (self.env.now,resp.getAckNum())
        self.dest.links[0].sendData(resp,self.dest)
      elif self.nextAck == packet.getSeqNum():
        resp.setHeader(src=self.dest.name, dest=self.src.name,
                      seq=seqnum, ack=packet.getSeqNum())
        self.unacked.append(resp)
        self.unacked.sort(key=lambda pkt: pkt.getAckNum())
        while len(self.unacked)>0 and self.nextAck == self.unacked[0].getAckNum():
          resp = self.unacked.pop(0)
          self.nextAck = resp.getAckNum()+1
#        print "%f: Responding with %d" % (self.env.now,resp.getAckNum())
        self.dest.links[0].sendData(resp,self.dest)
