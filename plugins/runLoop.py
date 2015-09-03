#!/usr/bin/env python
import time
import loader
from datetime import datetime
i=0
confFile,interval=loader.parseArgs()
while True:
	while datetime.now().second==0:
		i+= 1
		print i
		t =time.time()
		loader.main(confFile)
		time.sleep(interval-0.5-(time.time()-t))
	time.sleep(0.5)
