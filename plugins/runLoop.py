#!/usr/bin/env python
import time
import loader
from datetime import datetime
i=0
while True:
	while datetime.now().second==0:
		i+= 1
		print i
		t =time.time()
		loader.main()
		time.sleep(59.5-(time.time()-t))
	time.sleep(0.5)
