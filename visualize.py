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
    if line.find("FLOW")==0:
      blah,time,name,cwnd,data,rtt,rate,state = line.split(',')
      if name not in flows:
        flows[name] = [[],[],[],[],[],[]]
      flows[name][0].append(time)
      flows[name][1].append(cwnd)
      flows[name][2].append(data)
      flows[name][3].append(rtt)
      flows[name][4].append(rate)
      flows[name][5].append(state)
  return flows

def visbuf(logfile):
  f = open(logfile)
  links = {}
  for line in f:
    line = line.strip()
    if line.find("BUF")==0:
      blah,time,name,bufsz,buflen,blah = line.split(',')
      if name not in links:
        links[name] = [[],[],[]]
      links[name][0].append(time)
      links[name][1].append(bufsz)
      links[name][2].append(buflen)
  return links

links = visbuf('test2_reno2.log')
for link in links:
  links[link] = np.array(links[link])

flows = viscwn('test2_reno2.log')
for flow in flows:
  flows[flow] = np.array(flows[flow])

def plotlink(nm,j,ylabel='Buffer data (bytes)'):
  i=0
  if isinstance(nm,list):
    for n in nm:
      if n in links:
        plt.plot(links[n][i],links[n][j],label=n)
      plt.legend()
  else:
    plt.plot(links[n][i],links[n][j])
  plt.xlabel('time (s)')
  plt.ylabel(ylabel)

def plotflow(nm,j,ylabel='Congestion Window Size',state=False):
  i=0

  if state and not isinstance(nm,list):
    r = (1,0,0)
    g = (0,1,0)
    b = (0,0,1)
    clrs = np.zeros((flows[nm][3].shape[0],3))
    clrs[flows[nm][-1]=='SS']=g
    clrs[flows[nm][-1]=='CA']=b
    clrs[flows[nm][-1]=='FR']=r
    points = np.array([flows[nm][i], flows[nm][j]]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)

    lc = LineCollection(segments, colors=clrs)
    lc.set_linewidth(1.7)
    fig, ax = plt.subplots()
    ax.add_collection(lc)
    ax.autoscale_view()

    line_ss = mlines.Line2D([], [], color='green', label='Slow Start')
    line_ca = mlines.Line2D([], [], color='blue', label='Congestion Avoidance')
    line_fr = mlines.Line2D([], [], color='red', label='Fast Recovery')
    plt.legend(handles=[line_ss,line_ca,line_fr])
  else:
    if isinstance(nm,list):
      for n in nm:
        if n in flows:
          plt.plot(flows[n][i],flows[n][j],label=n)
    else:
      plt.plot(flows[nm][i],flows[nm][j])
    plt.legend()
  plt.xlabel('time (s)')
  plt.ylabel(ylabel)
  plt.show()


