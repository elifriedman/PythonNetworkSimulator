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
    self.buffer = simpy.Store(env)

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
    dest = packet.header['dest']
    if dest in self.routingtable:
      link = self.routingtable[dest]
      othernode = link.getOtherNode(self).name
#      print "%s received %d. Forwarding to %s. Dest: %s" % (self.name,packet.header['index'],othernode,dest)
      self.routingtable[dest].sendData(packet,self)

class Host(Node):
  def __init__(self,name,env):
    Node.__init__(self,name,env)
    self.data = simpy.Store(env)

  def dataDelivery(self,packet):
    # flow will be alerted that we've received a packet
    self.data.put(packet)

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
#      print "Packet %s on buffer at time %f, bufsize: %d " % (str(packet.header),self.env.now,self.bufdata)
    else:
      pass
#      print "Packed %s dropped at time %f" % (str(packet.header), self.env.now)

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
  def __init__(self,pktsize,data=[],header=[],loginfo=[]):
    self.pktsize = pktsize
    self.data = data
    self.header = header
    self.loginfo = loginfo

  def __len__(self):
    return self.pktsize

class Flow:
  def __init__(self,name, src, dest, KBamount, start,env):
    self.name = name
    self.src = src
    self.dest = dest
    self.data = KBamount*1024 # bytes
    self.sentpackets = []
    self.start = start
    self.env = env
    self.action = env.process(self.runSrc())
    self.action = env.process(self.runDest())

  def runSrc(self):
    yield self.env.timeout(self.start)
    print "%s started at %f" % (self.name,self.env.now)
    pktsize = 1024
    i = random.randint(0,100)
    while self.data > 0:
      size = pktsize
      if self.data < pktsize:
        size = self.data
      header = {}
      header['index'] = i
      header['src'] = self.src.name
      header['dest'] = self.dest.name
      packet = Packet(size+len(header),header=header,loginfo=[self.env.now])
      self.sentpackets.append(packet)
      self.data -= len(packet)
      i += 1
      self.src.links[0].sendData(packet,self.src)
      ack = yield self.src.data.get()
      print "packet %d took %f seconds" % (ack.header['index'],self.env.now-ack.loginfo[0])

  def runDest(self):
    i = random.randint(0,100)
    while True:
      packet = yield self.dest.data.get()
      respheader = {}
      respheader['index']=i
      respheader['src'] = self.dest.name
      respheader['dest'] = self.src.name
      respheader['respindex'] = packet.header['index']
      i += 1
      resp = Packet(max(len(respheader),64),header=respheader,loginfo=packet.loginfo)
      self.dest.links[0].sendData(resp,self.dest)


s = Sim('Test2/netfile.csv',
'Test2/flowfile.csv',
'Test2/routingtable.csv')
s.env.run(until=20)