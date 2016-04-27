import simpy
import random
from numpy import inf

from node import *
from link import *
from flow import *

class Sim:
  """ A class for reading and loading the configuration files, and initializing
  everything.
  """
  def __init__(self,netfilename,flowfilename,routingfilename=None):
    self.env = simpy.Environment()
    self.nodes = self.getNodes(netfilename)
    self.flows = self.getFlows(flowfilename)
    for node in self.nodes:
      if isinstance(self.nodes[node],Router):
        for nodename in self.nodes:
          self.nodes[node].addNode(nodename)
        self.nodes[node].initDVRouting()

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
      name, src, dest, KBamount, start,tcptype = line.split(',')
      f = Flow(name,self.nodes[src],self.nodes[dest],int(KBamount),float(start),
               tcptype.lower(),self.env)
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
        else: nodes[n1] = Host(n1,self.env)
      if n2 not in nodes:
        if n2[0]=='R': nodes[n2] = Router(n2,self.env)
        else: nodes[n2] = Host(n2,self.env)

      l = Link(nodes[n1],nodes[n2],lname,
               int(lbuffer),float(lrate),float(ldelay),self.env)
      nodes[n1].addLink(l)
      nodes[n2].addLink(l)
    return nodes

import sys
if __name__=='__main__':
  if len(sys.argv) < 3:
    print "usage: python netsim.py Folder time"
    sys.exit(0)
  folder = sys.argv[1]+'/'
  netfile = folder+'netfile.csv'
  flowfile = folder+'flowfile.csv'
  time = float(sys.argv[2])
  s = Sim(netfile,flowfile)
  s.env.run(until=time)