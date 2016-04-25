import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.lines as mlines

def viscwn(logfile):
  f = open(logfile)
  flows = {}
  for line in f:
    line = line.strip()
    if line.find("CWND")==0:
      blah,time,name,cwnd,data,state = line.split(',')
      if name not in flows:
        flows[name] = [[],[],[],[]]
      flows[name][0].append(time)
      flows[name][1].append(cwnd)
      flows[name][2].append(data)
      flows[name][3].append(state)
  return flows

def visbuf(logfile):
  f = open(logfile)
  links = {}
  for line in f:
    line = line.strip()
    if line.find("BUF")==0:
      blah,time,name,bufsz,buflen = line.split(',')
      if name not in links:
        links[name] = [[],[],[]]
      links[name][0].append(time)
      links[name][1].append(bufsz)
      links[name][2].append(buflen)
  return links

links = visbuf('test2_reno.log')
for link in links:
  links[link] = np.array(links[link])

#plt.plot(links['L1'][0],links['L1'][1])
#plt.plot(links['L2'][0],links['L2'][1])
#plt.plot(links['L3'][0],links['L3'][1])
#plt.figure()
flows = viscwn('test2.log')

for flow in flows:
  flows[flow] = np.array(flows[flow])

def plotlink(nm,i,j):
  plt.plot(links[nm][i],links[nm][j])

def plotflow(nm,i,j,ylabel='Congestion Window Size'):
  r = (1,0,0)
  g = (0,1,0)
  b = (0,0,1)
  clrs = np.zeros((flows[nm][3].shape[0],3))
  clrs[flows[nm][3]=='SS']=g
  clrs[flows[nm][3]=='CA']=b
  clrs[flows[nm][3]=='FR']=r


  points = np.array([flows[nm][i], flows[nm][j]]).T.reshape(-1, 1, 2)
  segments = np.concatenate([points[:-1], points[1:]], axis=1)

  lc = LineCollection(segments, colors=clrs)
  lc.set_linewidth(1.7)
  fig, ax = plt.subplots()
  ax.add_collection(lc)
  ax.autoscale_view()
  plt.xlabel('time (s)')
  plt.ylabel(ylabel)

  line_ss = mlines.Line2D([], [], color='green', label='Slow Start')
  line_ca = mlines.Line2D([], [], color='blue', label='Congestion Avoidance')
  line_fr = mlines.Line2D([], [], color='red', label='Fast Recovery')
  plt.legend(handles=[line_ss,line_ca,line_fr])
  plt.show()
