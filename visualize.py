import numpy as np
import matplotlib.pyplot as plt

def viscwn(cwnfile):
  f = open(cwnfile)
  times = []
  cwnds = []
  for line in f:
    line = line.strip()
    if line.find("CWND")==0:
      blah,time,cwnd = line.split(',')
      times.append(float(time))
      cwnds.append(float(cwnd))
  plt.plot(times,cwnds)
  plt.show()
