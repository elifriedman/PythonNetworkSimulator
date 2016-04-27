import simpy
import random
from numpy import inf

from link import *
from flow import *

class Node:
  def __init__(self,name,env):
    self.name = name
    self.links = []
    self.linkmap = {}
    self.env = env
    self.distance_vecs = {name:{}}

  def addLink(self,link):
    self.links.append(link)
    self.linkmap[link.name] = link

  def addNode(self,nodename):
    self.distance_vecs[self.name][nodename] = inf

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
    """
    Delivers packets to their destinations by looking up the destination
    in the routing table to find the correct outgoing link.
    """
    dest = packet.getDest()
    if dest == self.name: # it's a distance vector update
      self.distance_vecs[packet.getSrc()] = packet.data
    elif dest in self.routingtable and packet.hopcount > 0:
      packet.hopcount -= 1
      self.routingtable[dest].sendData(packet,self)
    self.updateDVRouting()

  def updateDVRouting(self,send=False):
    """
    Updates the distance vectors and routing table so that for each node:

    dvec[me->node] = min_neighbor {dist(myself,neighbor) +  dvec(neighbor,node)}
    routingtable[me->node] = argmin_neighbor {dist(myself,neighbor) +  dvec(neighbor,node)}

    If the routing table changes, we send an update to each neighboring router.

    Parametrs
    ---------
    send : bool
           Send an update to our neighbors regardless of whether the dvec changes.
           (Useful when initializing the Distance Vector algorithm)
    """
    dvec = self.distance_vecs[self.name] # my distance vector
    changed = False
    for node in dvec:
      if node==self.name: continue
      mini = inf
      minlink = None
      for link in self.links:
        nb_name = link.getOtherNode(self).name
        if link.cost() + self.distance_vecs[nb_name][node] < mini:
          mini = link.cost() + self.distance_vecs[nb_name][node]
          minlink = link
      if mini != dvec[node]:
        changed = True
        dvec[node] = mini
        self.routingtable[node] = minlink
    if changed or send:
      # Now send my distance vec to my neighbors
      for link in self.links:
        if isinstance(link.getOtherNode(self),Router):
          pkt = Packet(0,None,data=self.distance_vecs[self.name])
          pkt.setHeader(src=self.name,dest=link.getOtherNode(self).name)
          link.sendData(pkt,self)
#      print self.name,':'
#      for node in self.distance_vecs:
#        print node,self.distance_vecs[node]
#      print dict((d,l.name) for d,l in self.routingtable.items())
#      print ""

  def initDVRouting(self):
    """
    Initializes the Distance Vector routing algorithm by finding the cost
    of this node's neighboring links and updating its distance vector. It
    intializes its neighbor's distance vector to inf.

    The node then sends its updated distance vector to its neighboring
    routers.
    """
    dvec = self.distance_vecs[self.name].copy()
    for link in self.links:
      neighbor = link.getOtherNode(self)
      nb_name = neighbor.name
      self.distance_vecs[self.name][nb_name] = link.cost() # update my dvec
      self.routingtable[nb_name] = link
      self.distance_vecs[nb_name] = dvec.copy() # initialize to inf
      self.distance_vecs[nb_name][nb_name] = 0 # set self cost to 0
    self.distance_vecs[self.name][self.name] = 0 # 0 cost to myself
    self.updateDVRouting(send=True)

class Host(Node):
  def __init__(self,name,env):
    Node.__init__(self,name,env)

  def dataDelivery(self,packet):
    packet.flow.dataDelivery(packet,self)