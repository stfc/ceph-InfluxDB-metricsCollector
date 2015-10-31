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
import sys

#set default locations of configuration files
script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
rel_path = "conf/default.conf"
defaultConf = os.path.join(script_dir, rel_path)
expectedConf = '/etc/ceph-influxdb-metricsCollector.conf'

def parseArgs():
	'''
	Parses the command line arguments given with the command.
	Currently the arguments it looks for are:
	-c and --config
	'''
	confPath = expectedConf
	interval = 60
	versionInfo = sys.version_info
	if versionInfo[0] <= 6 and versionInfo[0] == 2:
		#if version is 2.6.x use optparse
		from optparse import OptionParser
		parser = OptionParser()
		parser.add_option('-c','--config', dest='configPath',help='The FILE the config should be read from. By default reads from etc/ceph-influxDB-metricsCollector/ceph-influxDB-metricsCollector.conf',metavar='FILE')
		parser.add_option('-i','--interval', dest='interval',help='The length of time between the running of plugins, given in minutes. By default is set to 1 minute')
		options, args = parser.parse_args()
		options=options.__dict__
	else:
		#if version is newer use argparse
		from argparse import ArgumentParser
		parser = ArgumentParser(description='Gather metrics from the ceph cluster and send them to influxDB via the HTTP API using the line protocol')
		parser.add_argument('-c','--config', metAvar='FILE',dest='configPath')
		parser.add_argument('-i,','--interval', dest='interval')
		options = parser.parse_args()
	try:
		if not (options['configPath'] == '' or options['configPath'] == None):
			confPath = options['configPath']
	except:
		confPath = expectedConf
	try:
		if not (options['interval'] == '' or options['interval'] == None):
			interval = int(options['interval'])*60
	except:
		interval=60

	return confPath, interval


def main(configFile=defaultConf):
	'''
	Main function which gets the plugins, runs them and sends the resultant points to influxDB
	'''
	def loadPlugin(uri):
		'''
		imports the plugin from a relative URI
		returns the loaded plugin on success
		Returns None on failure
		'''
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
				logger.warning('Could not load the .py file:{0}'.format(e))
				pass
		return None

	def make_batches(points, size):
		'''
		Creates batches of points to be zipped and sent to influxDB
		'''
		for i in xrange(0, len(points), size):
			yield points[i:i + size]

	def parseConf(configFile):
		'''
		Reads and parses the configuration file.
		It also creates a reference to the logger created from the configuration file
		Returns options, plugins, logger
		If config file cannot be parsed, it loads the default config from conf/default.conf
		'''
		#create logger for startup file
		logger = createLogger('/var/log/ceph-influxdb-metricsCollector-startup.log')
		#create array for plugins
		plugins={}
		options={}
		try:
			#set up the config parser
			config = ConfigParser.ConfigParser()
			config.readfp(open(configFile))
			#try to read config file
			#reporting
			#create options dictionary
			options['clusters']={}
			#for each cluster get array of configurationFile,keyringFile
			for k,v in config.items('reporting'):
				#split list of conf,keyring by comma
				argList=v.split(',')
				c=argList[0]
				keyring=argList[1]
				if c=='none':
					c=None
				if keyring=='none':
					keyring=None
				options['clusters'][k]={'conf':c,'keyring':keyring}
			#hosts
			options['host'] = config.get('connection','host')
			options['port'] = config.get('connection','port')
			#connection settings
			options['db'] = config.get('connection','db')
			options['user'] = config.get('connection','user')
			options['password'] = config.get('connection','pass')
			options['ssl'] = config.getboolean('connection','ssl')
			options['verify_ssl'] = config.getboolean('connection','verify_ssl')
			options['retention_policy'] = config.get('connection','retention_policy')
			options['compresison_level'] = config.getint('connection','compresison_level')
			options['batch_size'] = config.getint('connection','batch_size')
			#load logging settings
			options['loggingPath'] = config.get('logging','path')
			options['loggingLevel'] = config.get('logging','level')
			#load plugins
			for k,v in config.items('plugins'):
				#remove outer brackets
				v=v.strip('[]')
				plugins[k]=set(v.split(','))
		except Exception as e:
			logger.critical('The' + str(configFile) +' file is misconfigured. Cannot load configuration: {0}'.format(e))
			#use default configuration
			return parseConf(defaultConf)

		#if retention policy set to 'none', set to None
		if options['retention_policy'].lower() == 'none':
			retention_policy=None

		#format the path into an absolute path to the directory of the log
		if '[BaseDirectory]' in options['loggingPath']:
			options['loggingPath'] = os.path.join(script_dir,options['loggingPath'][16:])

		#format the value of level into the ENUM equivalent
		if options['loggingLevel'] in ('DEBUG','INFO','WARNING','ERROR','CRITICAL'):
			options['loggingLevel'] = logging.__getattribute__(options['loggingLevel'])
		else:
			#anything else set to default
			logger.warning('Could not understand logging option: "{0}". Defaulting to level WARNING'.format(options['loggingLevel']))
			options['loggingLevel'] = logging.WARNING

		try:
			#make path to the log file
			options['loggingPath'] = os.path.join(options['loggingPath'],'ceph-influxdb-metricsCollector.log')
			#get logger
			logger = createLogger(options['loggingPath'],loggingLevel=options['loggingLevel'])
		except Exception as e:
			logger.critical('The' + configFile +' file is misconfigured. Cannot create logger: {0}'.format(e))
			#Use default configurations
			return parseConf(defaultConf)

		return options, plugins, logger

	def createLogger(loggingPath,loggingLevel=logging.INFO):
		'''
		This function removes and closes all previous handlers and then creates a file handler for the logging file, assigns it to the logger, and returns a reference to the logger
		Returns a reference to the logger class
		'''
		#create logger
		logger = logging.getLogger('ceph-influxDB-metricsCollector')
		#delete previous handlers
		for h in logger.handlers:
			h.close()
		logger.handlers=[]
		#create handler for file
		handler = logging.FileHandler(loggingPath)
		# create a logging format
		formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
		handler.setFormatter(formatter)
		# add the handlers to the logger
		logger.addHandler(handler)
		logger.setLevel(loggingLevel)
		logger.propagate = False
		return logger

	

	options, plugins, logger = parseConf(configFile)
	logger.info('-----------------------Starting script------------------------')
	#create empty list for all points
	points=[]
	#for each cluster get the dictionary that contains keychain and configFile
	for cluster,clusterDict in options['clusters'].iteritems():
		
		#Make sure cache did not persist from previous run
		cache={}
		reload(base)
		logger.info('Retrieving metrics from cluster "{0}"'.format(cluster))
		#for each plugin get the set of clusters it should run on
		for p,clusterSet in plugins.iteritems():
			if cluster in clusterSet:
				#load plugin and return reference to loaded module
				plugin = loadPlugin(p)
				if not plugin == None:
					#find all classes in module
					clsmembers = inspect.getmembers(plugin, inspect.isclass)
					found = False
					#iterate through classes in module to find classes that inherit from base.Base
					for i in range(0,len(clsmembers)):
						name,cls = clsmembers[i]
						#check if class is a sub class of base
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
								logger.error('Plugin "{0}" failed to run: {1} :: {2}'.format(p,exc,traceback.format_exc()))
							
						else:
							logger.debug('Class "{0}" does not inherit from base.Base'.format(name))


					if not found:
						logger.warning('Plugin "{0}" not executed. Did not find any classes that inherit from base.Base'.format(p))

				else:
					logger.warning('Could not load plugin: "{0}"'.format(p))
		logger.info('Finished retrieving metrics for cluster "{0}"'.format(cluster))
	logger.info('Total points collected: {0}'.format(len(points)))
	try:
		
		#create connection to influxDB - see influxDB-python for more information
		logger.info('Opening connection to "{0}:{1}" as "{2}" to database "{3}"'.format(options['host'],options['port'],options['user'],options['db']))
		client = InfluxDBClient(options['host'],options['port'], options['user'], options['password'], options['db'], options['ssl'], options['verify_ssl'])

		#create parameters
		params = {'db':options['db'],'precision':'ms'}
		#set optional parameters
		if options['retention_policy'] is not None:
			params['rp'] = options['retention_policy']
		if options['batch_size'] == 0:
			options['batch_size'] = len(points)
		#Create batches from points of specified size
		for batch in make_batches(points,options['batch_size']):
			logger.info('Writing batch')
			#make continous string from array
			batch = '\n'.join(points)
			#create a new string memory buffer as temporary file
			f = cStringIO.StringIO()
			#zip points into file
			fzip = gzip.GzipFile(fileobj=f, mode="wb",compresslevel=options['compresison_level']).write(batch)
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
		logger.critical('Failed to write points to "{0}:{1}" with options: time_precision:"ms", retention_policy:"{2}" Error:"{3}" Traceback:"{4}"'.format(options['host'],options['port'],options['retention_policy'],exc,traceback.format_exc()))
	#Dispose of handlers
	for h in logger.handlers:
		h.close()
		logger.handlers=[]





#Start main function if not initiated from outside script
if __name__ == '__main__':
	#parse config arguments given in command line
	confPath=parseArgs()[0]
  	main(confPath)
