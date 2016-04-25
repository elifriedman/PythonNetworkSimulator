import simpy
import random
from numpy import inf

from node import *

class Link:
  def __init__(self,node1,node2,name,bufsz,linkrate,propdelay,env):
    self.nodes = [node1,node2]
    self.name = name
    self.bufsz = bufsz*1024 # bytes
    self.buffer = []
    self.bufdata = 0
    self.link = simpy.Store(env,capacity=1)
    self.linkrate = linkrate*1024**2 # bytes
    self.propdelay = propdelay * 1E-3 # seconds
    self.env = env
    self.action = env.process(self.run())
    self.linkoccpuied = False

  def getOtherNode(self,node):
    if node == self.nodes[0]:
      return self.nodes[1]
    if node == self.nodes[1]:
      return self.nodes[0]

  def sendData(self,packet,fromNode):
    if not self.linkoccpuied and self.bufdata == 0:
      self.linkoccpuied = True
      self.link.put((packet,self.getOtherNode(fromNode)))
    elif self.bufdata + len(packet) <= self.bufsz:
      self.buffer.append((packet,self.getOtherNode(fromNode)))
      self.bufdata += len(packet)
    else:
      pass

  def linkDelay(self,datasize):
    return datasize/self.linkrate

  def cost(self):
    return 1.0/self.linkrate #self.bufdata/self.linkrate + 1# use hopcount as cost

  def run(self):
    while True:
      link_packet,link_otherNode = yield self.link.get()
      yield self.env.timeout(self.linkDelay(len(link_packet)))
      self.linkoccpuied = False
      if self.bufdata > 0:
        packet,otherNode = self.buffer.pop(0)
        self.bufdata -= len(packet)
        self.linkoccpuied = True
#        print "Packet %s on link from buf at time %f, bufsize: %d" % (str(packet.header),self.env.now,self.bufdata)
        self.link.put((packet,otherNode))

      yield self.env.timeout(self.propdelay)
#      print "Packet %s off link at time %f" % (str(link_packet.header),self.env.now)
      link_otherNode.dataDelivery(link_packet)
      print "BUF,%f,%s,%d,%d" % (self.env.now,self.name,self.bufdata,len(self.buffer))

class Packet:
  def __init__(self,pktsize,flow,data=[],loginfo=[]):
    self.pktsize = pktsize
    self.flow = flow
    self.data = data
    self.loginfo = loginfo
    self.setHeader()

  def setHeader(self,src="",dest="",seq=-1,ack=-1,isack=False):
    self.header = {'src':src,'dest':dest,
                   'seqnum':seq,'acknum':ack,
                   'isack':isack}
  def getSrc(self):
    return self.header['src']
  def getDest(self):
    return self.header['dest']
  def getSeqNum(self):
    return self.header['seqnum']
  def getAckNum(self):
    return self.header['acknum']
  def isAck(self):
    return self.header['isack']
  def __len__(self):
    return self.pktsize