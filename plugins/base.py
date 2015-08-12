import traceback
import logging
import os 
import collections
import functools
from  influxLineProtocol import createLineProtocolStatement
import json

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

	def __init__(self,cluster,cache,timestamp):
		self.cluster=cluster
		self.user=''
		self.password=''
		self.db=''
		self.host=''
		self.port=8086
		#get application self.logger
		self.logger = logging.getLogger('ceph-influxDB-metricsCollector')
		#set cache
		mainCache=cache
		self.timestamp=timestamp

	@memoized
	def execute_command(self,returnJSON,*args):
		self.logger.debug('Command is not memorized')
		#call command
		self.logger.info('Executing command:{0}'.format(args))
		output = ''
		
		try:
			output = os.popen2(' '.join(args))[1].read()
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
		self.logger.debug("JSON is not memorized")
		#try reading json file
		try:
			return json.loads(jsonFile)
		except Exception as exc:
			self.logger.error('JSON cannot be converted into a python object:"{0}"'.format(exc))
			self.logger.debug('JSON file:"{0}"'.format(jsonFile))
			return None

	def create_measurement(self,tags,fields):
		return make_line(self.cluster,tags,fields,self.timestamp)

	def gather_metrics(self):
		self.logger.warning('function has not been sub classed')
		return []

	@memoized
	def get_pool_names(self):
		#create a dicitonary of poolid-->poolname for conversion
		output = self.execute_command(True,'ceph','osd','lspools','--format','json')

		if output == None or output == {}:
			self.logger.warning('No output recieved from "ceph osd lspools --format json"')
			return []

		poolIds = {}

		for pool in output:
			poolIds[str(pool['poolnum'])]=pool['poolname']
		return poolIds


