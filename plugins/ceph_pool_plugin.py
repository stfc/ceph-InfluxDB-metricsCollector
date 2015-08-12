import base

class CephPluginPoolData(base.Base):
	def __init__(self,cluster,cache,timestamp,c,k):
		#initialise

		base.Base.__init__(self,cluster,cache,timestamp,c,k)
		#create dictionary to find data protection types of different pools
		self.poolDPType={}
		#create array of all statistics to fetch from pg dump
		self.fetchStats = ['num_objects_degraded','num_objects_omap','num_objects_hit_set_archive','num_bytes_hit_set_archive','num_bytes_recovered','num_keys_recovered']

	def gather_metrics(self):
		self.logger.info('Gathering metrics')
		#create dictionary of pool data protection types
		self.get_pool_DPTypes()
		points = []

		points.extend(self.get_pool_metadata())
		points.extend(self.get_pool_storage_stats())
		points.extend(self.get_pool_io_stats())
		points.extend(self.get_pool_pg_data())

		return points

	def get_pool_DPTypes(self):
		output = self.execute_command(True,'ceph','osd','dump','--format','json')

		if output == None or output=={}:
			self.logger.error('No output recieved from "ceph osd dump --format json"')
		else:
			#Write to dictionary the data protection type
			for pool in output['pools']:
				poolName = pool['pool_name']
				dataProtectionType = pool['erasure_code_profile']
				if dataProtectionType == '':
					dataProtectionType = 'Replication'
				self.poolDPType[poolName]=dataProtectionType

	def get_pool_storage_stats(self):
		'''
		metrics collected:
			-bytes_used
			-max_avail
			-objects
		'''
		#run ceph command
		self.logger.info('Getting pool storage stats')
		output = self.execute_command(True,'ceph','df','--format','json')

		if output == None:
			self.logger.error('No output recieved from "ceph df --format json"')
			return []

		points = []
		#Get pool storage data
		for pool in output['pools']:
			poolName = pool['name']
			for stat in ('bytes_used', 'max_avail', 'objects'):
				statValue = pool['stats'][stat] if pool['stats'].has_key(stat) else 0
				try:
					points.append(self.create_pool_measurement(poolName,self.poolDPType[poolName],stat,statValue))
				except Exception as e:
					self.logger.warning("Could not write point: {0}".format(e))

		return points

	def get_pool_io_stats(self):
		'''
		metrics collected:
			-read_bytes_sec
			-write_bytes_sec
			-op_per_sec
		'''
		#run ceph command
		self.logger.info('Getting pool io stats')
		output = self.execute_command(True,'ceph','osd','pool','stats','--format','json')

		if output == None:
			self.logger.error('No output recieved from "ceph osd pool stats --format json"')
			return []

		points = []
		#Get pool io data
		for pool in output:
			poolName = pool['pool_name']
			for stat in ('read_bytes_sec', 'write_bytes_sec', 'op_per_sec'):
				statValue = pool['client_io_rate'][stat] if pool['client_io_rate'].has_key(stat) else 0
				try:
					points.append(self.create_pool_measurement(poolName,self.poolDPType[poolName],stat,statValue))
				except Exception as e:
					self.logger.warning("Could not write point: {0}".format(e))
				

		return points

	def get_pool_metadata(self):
		'''
		metrics collected:
			-size
			-pg_num
			-pg_placement_num
		'''
		#run ceph command
		self.logger.info('Getting pool metadata')
		output = self.execute_command(True,'ceph','osd','dump','--format','json')

		if output == None:
			self.logger.error('No output recieved from "ceph osd dump --format json"')
			return []

		points = []
		#Get pool metadata
		for pool in output['pools']:
			poolName = pool['pool_name']
			for stat in ('size','pg_num','pg_placement_num'):
				statValue = pool[stat] if pool.has_key(stat) else 0
				try:
					points.append(self.create_pool_measurement(poolName,self.poolDPType[poolName],stat,statValue))
				except Exception as e:
					self.logger.warning("Could not write point: {0}".format(e))
		return points

	def get_pool_pg_data(self):
		'''
		metrics collected:
			-num_objects_degraded
			-num_objects_omap
			-num_objects_hit_set_archive
			-num_bytes_hit_set_archive
			-num_bytes_recovered
			-num_keys_recovered
		'''
		#run ceph command
		self.logger.info('Getting pg data')
		output = self.execute_command(True,'ceph','pg','dump','--format','json')
		poolIDs=self.get_pool_names()
		if output == None or output == {}:
			self.logger.warning('No output recieved from "ceph pg dump --format json"')
			return []
		points = []
		try:
			for pool in output['pool_stats']:
				poolName=poolIDs[str(pool['poolid'])]
				statSums = pool['stat_sum']
				for stat in self.fetchStats:
					points.append(self.create_pool_measurement(poolName,self.poolDPType[poolName],stat,statSums[stat]))
		except Exception as e:
			self.logger.error('Couldnt collect pool statistics about pgs: {0}'.format(e))
			return []
		return points



	def create_pool_measurement(self, poolName, dataProtectionType, metricName, value):
		tags = {'type':'pool','dataProtectionType':dataProtectionType, 'pool':poolName,'metric':metricName}
		fields = {'value':value}
		return self.create_measurement(tags,fields)