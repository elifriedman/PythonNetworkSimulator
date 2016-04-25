import numpy as np
import matplotlib.pyplot as plt

def viscwn(logfile):
  f = open(logfile)
  flows = {}
  for line in f:
    line = line.strip()
    if line.find("CWND")==0:
      blah,time,name,cwnd = line.split(',')
      if name not in flows:
        flows[name] = [[],[]]
      flows[name][0].append(time)
      flows[name][1].append(cwnd)
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

links = visbuf('test3.log')
for link in links:
  links[link] = np.array(links[link])

#plt.plot(links['L1'][0],links['L1'][1])
#plt.plot(links['L2'][0],links['L2'][1])
#plt.plot(links['L3'][0],links['L3'][1])
#plt.figure()
flows = viscwn('test3.log')

for flow in flows:
  flows[flow] = np.array(flows[flow])

plt.plot(flows['F1'][0],flows['F1'][1])
plt.plot(flows['F2'][0],flows['F2'][1])
plt.plot(flows['F3'][0],flows['F3'][1])