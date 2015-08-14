import base

class CephPGPlugin(base.Base):
	def __init__(self,cluster,cache,timestamp,c,k):
		#initialise
		base.Base.__init__(self,cluster,cache,timestamp,c,k)

	def gather_metrics(self):
		'''
		Subclassed method of base.py which is called by loader.py
		Returns array of points collected by the plugin
		'''
		self.logger.info('Gathering metrics')
		#get ids of pools and their corresponding names
		poolIds = self.get_pool_names()
		#Define which stats we want to get
		fetchStats = ['num_bytes','num_objects']


		#run ceph command
		output = self.execute_command(True,'ceph','pg','dump','--format','json')

		if output == None or output == {}:
			self.logger.warning('No output recieved from "ceph pg dump --format json"')
			return []
		points = []

		#create variable for the create_measurement method - improves performance
		create_measurement = self.create_measurement
		#get sums of stats across pgs
		pgOverallStats = output['pg_stats_sum']
		'''
		List of stats taken from pgOverallStats:
		|	stat_sum
		|		|----------------------------------
		|		|	num_bytes #Total bytes used by pg
		|		|	num_objects #Total number of objects stored in pg
		|		-----------------------------------
		------------------------------------------------------
		'''

		stat_sum = pgOverallStats['stat_sum']

		#get all the attributes from stat_sum
		for subStat in fetchStats:
			points.append(create_measurement(
				{'type':'pg','pool':'All','pg':'sum','metric':subStat},
				{'value':stat_sum[subStat]}))

		#get stats per pg
		pgStats = output['pg_stats']
		'''
		Needs refining. List of stats taken from pgStats:
		|	state
		|	stat_sum
		|		|----------------------------------
		|		|	num_bytes #Total storage space used?
		|		|	num_objects #Total number of objects stored in pg
		|		|-----------------------------------
		|
		------------------------------------------------------
		'''

		#count number of pgs in each state
		pgStates={}


		for pg in pgStats:
			#Parse the stat sums
			pgID = pg['pgid']
			poolName = poolIds[str(pgID.split('.')[0])]
			statSums = pg['stat_sum']
			state =  pg['state']
			for stat in fetchStats:
				points.append(create_measurement(
					{'type':'pg', 'pool':poolName,'pg':pgID,'state':state,'metric':stat},
					{'value':statSums[stat]}))


		return points
