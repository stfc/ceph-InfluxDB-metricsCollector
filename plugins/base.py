import traceback
import logging 
import collections
import functools
from  influxLineProtocol import createLineProtocolStatement
try:
	import simplejson as json
except:
	import json
import sys
import subprocess
import re

versionInfo = sys.version_info

mainCache = {}
make_line = createLineProtocolStatement

class memoized(object):
	 '''Decorator. Caches a function's return value each time it is called.
	 If called later with the same arguments, the cached value is returned
	 (not reevaluated).
	 '''
	 def __init__(self, func):
		self.func = func
		self.logger = logging.getLogger('ceph-influxDB-metricsCollector')
	 def __call__(self, *args):
		self.logger.info('Retrieving information from memoized')
		self.logger.debug('Function arguments:"{0}"'.format(args))
		#create argument list without name of calling class - alows multiple modules to use the same results
		argList = list(args)
		del argList[0]
		argsNoClass=tuple(argList)

		if not isinstance(args, collections.Hashable):
		 # uncacheable. a list, for instance.
		 # better to not cache than blow up.
		 self.logger.info('Unable to cache as it is unhashable: {0}'.format(args))
		 return self.func(*args)

		if argsNoClass in mainCache:
		 self.logger.info('Result found in cache')
		 return mainCache[argsNoClass]

		else:
		 self.logger.info('Result not found in cache')
		 value = self.func(*args)
		 mainCache[argsNoClass] = value
		 return value
		 
	 def __repr__(self):
		'''Return the function's docstring.'''
		return self.func.__doc__
	 def __get__(self, obj, objtype):
		'''Support instance methods.'''
		return functools.partial(self.__call__, obj)

class Base(object):

	def __init__(self,cluster,cache,timestamp,c,k):
		self.cluster=cluster
		self.clusterConf=c
		self.clusterKey=k
		self.clusterClientID=None
		#get application self.logger
		self.logger = logging.getLogger('ceph-influxDB-metricsCollector')
		#set cache
		mainCache=cache
		self.timestamp=timestamp
		if not self.clusterKey == None:
			self.extractClientID()


	def extractClientID(self):
		with open(self.clusterKey,'r') as f:
			data=f.read()
		client = re.search('(?<=\[client.).*(?=\])',data)
		self.clusterClientID=client.group(0)


	@memoized
	def execute_command(self,returnJSON,*args):
		'''
		Executes the command passed in. If specified, it will convert output to JSON format
		If the command is ceph related, it will add keychain and config file info.
		If it cannot execute or convert the command form JSON, it will return None
		'''
		self.logger.debug('Command is not memorized')
		#call command
		self.logger.info('Executing command:{0}'.format(args))
		output = ''
		if args[0]=='ceph':
			args=list(args)
			#add path to key, config and id if non default is specified
			if not self.clusterClientID==None:
				args.insert(1,'--id')
				args.insert(2,self.clusterClientID)
			if not self.clusterKey==None:
				args.insert(1,'-k')
				args.insert(2,self.clusterKey)
			if not self.clusterConf==None:
				args.insert(1,'-c')
				args.insert(2,self.clusterConf)

		args=tuple(args)
		try:
			if versionInfo[0] == 2 and versionInfo[1] <= 6:
				# if version earlier or equal to 2.6.x, use subprocess.Popen
				process = subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,close_fds=True)
				output = process.stdout.read()
				process.terminate()
			else:
				# For newer versions use subprocess
				output = subprocess.check_output(args,stdout=subprocess.PIPE)

		except Exception as exc:
			self.logger.error("Failed to execute command :: {0} :: {1}".format(exc, traceback.format_exc()))
			return None

		if returnJSON:
			#return converted json
			self.logger.info('Converting command output into python object')
			return self.readJson(output)
		else:
			#return result of command
			return output

	@memoized
	def readJson(self,jsonFile):
		'''
		converts JSON into dictionaries.
		If it cannot convert the JSON, it will return None

		'''
		self.logger.debug("JSON is not memorized")
		#try reading json file
		try:
			return json.loads(jsonFile)
		except Exception as exc:
			self.logger.error('JSON cannot be converted into a python object:"{0}"'.format(exc))
			self.logger.debug('JSON file:"{0}"'.format(jsonFile))
			return None

	def create_measurement(self,tags,fields):
		'''
		Encodes the tags and fields itno the influxDB line protocol.
		This calls the function make_line in influxLineProtocol.py

		'''
		return make_line(self.cluster,tags,fields,self.timestamp)

	def gather_metrics(self):
		'''
		This function is called by loader.py, and should be subclassed by the plugins.
		This function should return an array of points, already formatted by the create_measurement function.
		'''
		self.logger.warning('function has not been subclassed')
		return []

	@memoized
	def get_pool_names(self):
		'''
		This function creates and returns a dictionary associating pool names to pool ids in the format {poolID:poolName}
		'''
		#create a dicitonary of poolid-->poolname for conversion
		output = self.execute_command(True,'ceph','osd','lspools','--format','json')

		if output == None or output == {}:
			self.logger.warning('No output recieved from "ceph osd lspools --format json"')
			return []

		poolIds = {}

		for pool in output:
			poolIds[str(pool['poolnum'])]=pool['poolname']
		return poolIds


