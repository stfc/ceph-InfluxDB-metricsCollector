#!/usr/bin/env python
import os	
import imp
import ConfigParser
import inspect
import logging
from influxdb import InfluxDBClient
import base
import traceback
import gzip
import cStringIO
import traceback
import time

def main():
	def loadPlugin(uri):
		#turn relative path into absolute path
		uri = os.path.normpath(os.path.join(os.path.dirname(__file__), uri))
		path, fname = os.path.split(uri)
		mname, ext = os.path.splitext(fname)
		no_ext = os.path.join(path, mname)

		logger.info('Loading plugin from path: %s',no_ext)

		if os.path.exists(no_ext + '.pyc'):
			#try loading .pyc file
			try:
				return imp.load_compiled(mname, no_ext + '.pyc')
			except Exception as e:
				logger.info('Could not load the .pyc file:{0}'.format(e))
				pass
		if os.path.exists(no_ext + '.py'):
			#try loading .py file
			try:
				return imp.load_source(mname, no_ext + '.py')
			except Exception as e:
				logger.info('Could not load the .py file:{0}'.format(e))
				pass
		return None

	def make_batches(points, size):
		for i in xrange(0, len(points), size):
			yield points[i:i + size]

	#get location of configuration file
	script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
	rel_path = "conf/ceph-influxDB-metricsCollector.ini"
	ini_file = os.path.join(script_dir, rel_path)


	logger = logging.getLogger('ceph-influxDB-metricsCollector')
	#set default logging in case it cannot read the config
	loggingPath = os.path.join(script_dir,'logs/startup.log')
	#set default logging level
	loggingLevel = logging.INFO
	handler = logging.FileHandler(loggingPath)
	# create a logging format
	formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
	handler.setFormatter(formatter)
	# add the handlers to the logger
	logger.addHandler(handler)
	logger.setLevel(loggingLevel)
	logger.propagate = False
	

	#create array for plugins
	plugins=[]

	#create variables for config
	clusters = {}
	host = ''
	port = ''
	db = ''
	user = ''
	password = ''
	ssl=False
	verify_ssl = False
	retention_policy =''
	time_precision = 'ms'

	
	try:
		#set up the config parser
		config = ConfigParser.ConfigParser()
		config.readfp(open(ini_file))
		#try to read config file
		#reporting
		for k,v in config.items('reporting'):
			#split list of conf,keyring by comma
			argList=v.split(',')
			c=argList[0]
			keyring=argList[1]
			if c=='none':
				c=None
			if k=='none':
				keyring=None
			clusters[k]={'conf':c,'keyring':keyring}
		#hosts
		host = config.get('connection','host')
		port = config.get('connection','port')
		#connection settings
		db = config.get('connection','db')
		user = config.get('connection','user')
		password = config.get('connection','pass')
		ssl = config.getboolean('connection','ssl')
		verify_ssl = config.getboolean('connection','verify_ssl')
		retention_policy = config.get('connection','retention_policy')
		compresison_level = config.getint('connection','compresison_level')
		batch_size = config.getint('connection','batch_size')
		#load logging settings
		loggingPath = config.get('logging','path')
		loggingLevel = config.get('logging','level')
		#load plugins
		for k,v in config.items('plugins'):
			if v =='True':
				plugins.append(k)
	except:
		logger.critical('The ceph_tagging.ini file is misconfigured. Cannot load configuration.')
		#stop the execution of the script: no point running it if it does not have plugins to run or a database to connect to
		return

	#if retention policy se to 'none', set to None
	if retention_policy.lower() == 'none':
		retention_policy=None


	#format the path into an absolute path to the directory of the log
	if '[BaseDirectory]' in loggingPath:
		loggingPath = os.path.join(script_dir,loggingPath[16:])

	#format the value of level into the ENUM equivalent
	if loggingLevel == 'DEBUG':
		loggingLevel = logging.DEBUG
	elif loggingLevel == 'INFO':
		loggingLevel = logging.INFO
	elif loggingLevel == 'WARNING':
		loggingLevel = logging.WARNING
	elif loggingLevel == 'ERROR':
		loggingLevel = logging.ERROR
	elif loggingLevel == 'CRITICAL':
		loggingLevel = logging.CRITICAL
	else:
		#anything else set to default
		logger.warning('Could not understand logging option: "{0}". Defaulting to level WARNING'.format(loggingLevel))
		loggingLevel = logging.WARNING

	handler.close()
	logger.removeHandler(handler)
	#make path to the log file
	loggingPath = os.path.join(loggingPath,'ceph-influxDB-metricsCollector.log')
	#change the default logger to use the options selected
	handler = logging.FileHandler(loggingPath)
	# create a logging format
	handler.setFormatter(formatter)
	#remove previous handlers
	logger.handlers = []
	# add the handlers to the logger
	logger.addHandler(handler)
	logger.setLevel(loggingLevel)
	logger.propagate = False
	#Make sure cache did not persist from previous run
	reload(base)
	logger.info('-----------------------Starting script------------------------')
	#create empty list for all points
	cache={}
	points=[]
	for cluster,clusterDict in clusters.iteritems():
		logger.info('Retrieving metrics from cluster "{0}"'.format(cluster))
		for p in plugins:
			#load plugin
			plugin = loadPlugin(p)
			if not plugin == None:
				#find all classes in module
				clsmembers = inspect.getmembers(plugin, inspect.isclass)
				found = False
				#iterate through classes in module to find classes that inherit from base.Base
				for i in range(0,len(clsmembers)):
					name,cls = clsmembers[i]
					if issubclass(cls,base.Base):
						try:
							#create timestamp for plugin
							ts = int(round(time.time() * 1000))
							found = True
							#found class that inherits from base. Create instance
							instance = cls(cluster,cache,ts,clusterDict['conf'],clusterDict['keyring'])
							#Tell the plugin to collect information. Append the metrics collected to the points to be sent
							pointsReturned=instance.gather_metrics()
							logger.info('Plugin "{0}" created {1} points'.format(p,len(pointsReturned)))
							points.extend(pointsReturned)
							logger.info('Finished executing plugin "{0}"'.format(p))
						except Exception as exc:
							logger.error('Plugin "{0}" failed to run: {1} :: {3}'.format(p,exc,traceback.format_exc()))
						
					else:
						logger.debug('Class "{0}" does not inherit from base.Base'.format(name))


				if not found:
					logger.warning('Plugin "{0}" not executed. Did not find any classes that inherit from base.Base'.format(p))

			else:
				logger.warning('Could not load plugin: "{0}"'.format(p))
		
	logger.info('Total points collected: {0}'.format(len(points)))
	try:
		
		#create connection to influxDB - see influxDB-python for more information
		logger.info('Opening connection to "{0}:{1}" as "{2}" to database "{3}"'.format(host,port,user,db))
		client = InfluxDBClient(host,port, user, password, db, ssl, verify_ssl)

		#create parameters
		params = {'db':db,'precision':'ms'}

		if retention_policy is not None:
			params['rp'] = retention_policy
		if batch_size ==0:
			batch_size = len(points)

		for batch in make_batches(points,batch_size):
			logger.info('Writing batch')
			#make continous string from array
			batch = '\n'.join(points)
			#create a new string memory buffer as temporary file
			f = cStringIO.StringIO()
			#zip points into file
			fzip = gzip.GzipFile(fileobj=f, mode="wb",compresslevel=compresison_level).write(batch)
			#get size of file in bytes
			size = f.tell()
			#go back to start of file
			f.seek(0, 0)
			#send data to influxDB
			client.request(url="write",
				method='POST',
				params=params,
				data=f,
				expected_response_code=204,
				headers={
					'Content-type': 'application/octet-stream',
					'Content-encoding':'gzip',
					'Accept': 'gzip,text/plain',
					'Transfer-Encoding':'application/gzip'
				})
			
			#Close string buffer
			f.close()
		logger.info('Finished writing points')
	except Exception as exc:
		logger.critical('Failed to write points to "{0}:{1}" with options: time_precision:"{2}", retention_policy:"{3}" Error:"{4}" Traceback:"{5}"'.format(host,port,time_precision,retention_policy,exc,traceback.format_exc()))
	logger.info('--------------------Finished executing all scripts----------------------------')
	handler.close()
	logger.removeHandler(handler)
if __name__ == '__main__':
   main()
