import simpy
import random

class Sim:
  def __init__(self,netfilename,flowfilename,routingfilename=None):
    self.env = simpy.Environment()
    self.nodes = self.getNodes(netfilename)
    self.flows = self.getFlows(flowfilename)
    if routingfilename != None:
      self.routingtable = self.getRoutingTable(routingfilename)

  def getRoutingTable(self,routingfilename):
    f = open(routingfilename)
    for line in f:
      line = line.strip()
      if len(line)==0 or line[0]=='#':
        continue
      destination, routername, outgoing_link_name = line.split(',')
      self.nodes[routername].addRoute(destination,outgoing_link_name)


  def getFlows(self,flowfilename):
    ff = open(flowfilename)
    flows = []
    for line in ff:
      line = line.strip()
      if len(line)==0 or line[0]=='#':
        continue
      name, src, dest, KBamount, start = line.split(',')
      f = Flow(name,self.nodes[src],self.nodes[dest],int(KBamount),float(start),
               self.env)
      flows.append(f)
    return flows

  def getNodes(self,netfilename):
    nf = open(netfilename)
    nodes = {}
    for line in nf:
      line = line.strip()
      if len(line)==0 or line[0]=='#':
        continue
      lname,n1,n2,lrate,ldelay,lbuffer = line.split(',')
      if n1 not in nodes:
        if n1[0]=='R': nodes[n1] = Router(n1,self.env)
        elif n1[0]=='H': nodes[n1] = Host(n1,self.env)
      if n2 not in nodes:
        if n2[0]=='R': nodes[n2] = Router(n2,self.env)
        elif n2[0]=='H': nodes[n2] = Host(n2,self.env)

      l = Link(nodes[n1],nodes[n2],lname,
               int(lbuffer),float(lrate),float(ldelay),self.env)
      nodes[n1].addLink(l)
      nodes[n2].addLink(l)
    return nodes


class Node:
  def __init__(self,name,env):
    self.name = name
    self.links = []
    self.linkmap = {}
    self.env = env

  def addLink(self,link):
    self.links.append(link)
    self.linkmap[link.name] = link

  def dataDelivery(self,packet):
    pass

class Router(Node):
  def __init__(self,name,env):
    Node.__init__(self,name,env)
    self.routingtable = {}

  def addRoute(self,destination,linkname):
    if linkname in self.linkmap:
      outgoing_link = self.linkmap[linkname]
      self.routingtable[destination] = outgoing_link
    else:
      errstr = 'Link %s does not connect to node %s' % (linkname,self.name)
      raise Exception(errstr)

  def dataDelivery(self,packet):
    dest = packet.getDest()
    if dest in self.routingtable:
#      print "%s received %d. Forwarding to %s. Dest: %s" % (self.name,packet.header['index'],othernode,dest)
      self.routingtable[dest].sendData(packet,self)

class Host(Node):
  def __init__(self,name,env):
    Node.__init__(self,name,env)

  def dataDelivery(self,packet):
    packet.flow.dataDelivery(packet,self)

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
#      print "Packet %s on link at time %f" % (str(packet.header),self.env.now)
      self.linkoccpuied = True
      self.link.put((packet,self.getOtherNode(fromNode)))
    elif self.bufdata + len(packet) <= self.bufsz:
      self.buffer.append((packet,self.getOtherNode(fromNode)))
      self.bufdata += len(packet)
#      print "%s: %d" % (self.name,self.bufdata)
#      print "Packet %s on buffer at time %f, bufsize: %d " % (str(packet.header),self.env.now,self.bufdata)
    else:
      print "%f: %s dropped packet %d,%d" % (self.env.now,self.name,packet.getSeqNum(),packet.getAckNum())
      pass

  def linkDelay(self,datasize):
    return datasize/self.linkrate

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

class Flow:
  def __init__(self,name, src, dest, KBamount, start,env):
    self.name = name
    self.src = src
    self.srcdata = simpy.Store(env)
    self.dest = dest
    self.destdata = simpy.Store(env)
    self.data = KBamount*1024 # bytes
    self.start = start
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

      def fn():
        pkt = self.sentpackets[0]
        timeout = self.env.timeout(self.timeoutInterval())
        yield timeout
        if pkt in self.sentpackets:
          self.actionSrc.interrupt()
      self.env.process(fn())
      try:
        ackpkt = yield self.srcdata.get()

#        sampleRTT = self.env.now-self.rttracker[1]
#        self.estRTT = 0.875*self.estRTT + 0.125*sampleRTT
#        self.devRTT = 0.75*self.devRTT + 0.25*abs(sampleRTT-self.estRTT)
        while len(self.sentpackets) > 0 and \
              ackpkt.getAckNum() >= self.sentpackets[0].getSeqNum():
          self.ackCounter = 0
          self.sentpackets.pop(0)
#        if ackpkt.getAckNum() >= self.rttracker[0]:
#          sampleRTT = self.env.now - self.rttracker[1]
#          print "Updating %d with RTT %f, %f" % (ackpkt.getAckNum(),sampleRTT,self.timeoutInterval())
#          self.estRTT = 0.875*self.estRTT + 0.125*sampleRTT
#          self.devRTT = 0.75*self.devRTT + 0.25*abs(sampleRTT-self.estRTT)
#          self.rttracker[0] = seqnum
#          if ackpkt.getAckNum()==self.rttracker[0]:
#            self.rttracker[0] += 1
#          self.rttracker[1] = self.env.now

        if len(self.sentpackets) > 0 and \
              ackpkt.getAckNum()+1 == self.sentpackets[0].getSeqNum():
          self.ackCounter += 1
        print "CWND,%f,%d" % (self.env.now,self.cwnd)
        print "%f: packet %d (%f,%d,%d)" % (self.env.now,ackpkt.getAckNum(),self.timeoutInterval(),self.cwnd,len(self.sentpackets))

#        print "%f: packet %d took %f seconds (%f,%d,%d)" % (self.env.now,ackpkt.getAckNum(),sampleRTT,self.timeoutInterval(),self.cwnd,len(self.sentpackets))
        if self.ackCounter == 4:
          print "Resending %d" % self.sentpackets[0].getSeqNum()
          self.ackCounter = 0
          self.ssthresh = self.cwnd / 2
          self.cwnd = 0
          pkt = self.sentpackets[0]
          self.rttracker[0] = -1
          self.src.links[0].sendData(pkt,self.src)

        if self.cwnd >= self.ssthresh:
          self.cwndinc = 5.5/self.cwnd
        else:
          self.cwndinc = 1.0

        self.cwnd += self.cwndinc
      except simpy.Interrupt:
        self.ackCounter = 0
        self.cwnd = 1
        if len(self.sentpackets) > 0:
          pkt = self.sentpackets[0]
          self.rttracker[0] = -1
          print "%f: Timeout. Sent %d" % (self.env.now,pkt.getSeqNum())
          self.src.links[0].sendData(pkt,self.src)
        self.srcdata = simpy.Store(self.env)

  def runDest(self):
    seqnum = random.randint(0,100)
    self.nextAck = -1
    self.unacked = []
    while True:
      packet = yield self.destdata.get()
      print "%f: Received %d,%d" % (self.env.now,packet.getSeqNum(),self.nextAck)
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


s = Sim('Test2/netfile.csv',
'Test2/flowfile.csv',
'Test2/routingtable.csv')
s.env.run(until=250)