import base

class CephGeneralStatsPlugin(base.Base):
	def __init__(self,cluster,cache,timestamp,c,k):
		#initialise
		base.Base.__init__(self,cluster,cache,timestamp,c,k)

	def gather_metrics(self):
		'''
		Subclassed method of base.py which is called by loader.py
		Returns array of points collected by the plugin
		'''
		self.logger.info('Gathering metrics')
		points=[]

		try:
			points.extend(self.get_storage_stats())
			points.extend(self.get_quorum_stats())
		except Exception as e:
			self.logger.error('Did not manage to get general stats: {0}'.format(e))

		return points

	def get_storage_stats(self):
		'''
		Collects storage metrics about the cluster.
		Returns array of points, formatted into the format of the line protocol
		metrics collected:
			-total_bytes
			-total_used_bytes
			-total_avail_bytes
		'''
		self.logger.info('Getting storage metrics')
		#run ceph command
		output = self.execute_command(True,'ceph','df','--format','json')

		if output == None:
			self.logger.error('No output recieved from "ceph df --format json"')
			return []

		points = []

		clusterStats = output['stats']
		for stat in ('total_bytes', 'total_used_bytes', 'total_avail_bytes'):
				statValue = clusterStats[stat] if clusterStats.has_key(stat) else 0
				points.append(self.create_measurement(
					{'type':'general','metric':stat},
					{'value':statValue}))

		#calculate percentage space used
		percentage = (float(clusterStats['total_used_bytes'])/float(clusterStats['total_bytes']))*100
		points.append(self.create_measurement(
			{'type':'general','metric':'percentage_space_used'},
			{'value':percentage}))

		return points


	def get_quorum_stats(self):
		'''
		Collects monitor quorum metrics about the cluster.
		Returns array of points, formatted into the format of the line protocol
		metrics collected:
			-mons_up
			-quorum
			-ratio_in_quorum
		'''
		self.logger.info('Getting quorum metrics')
		#run ceph command
		output = self.execute_command(True,'ceph','mon','dump','--format','json')

		if output == None:
			self.logger.error('No output recieved from "ceph mon dump --format json"')
			return []

		points=[]
		monNum= len(output['mons'])
		quorum= len(output['quorum'])
		percentage = (quorum/monNum)*100
		#get number of monitors
		points.append(self.create_measurement({'type':'general','metric':'mons_up'},{'value':monNum}))
		#get number of monitors in quorum
		points.append(self.create_measurement({'type':'general','metric':'quorum'},{'value':quorum}))
		#get percentage
		points.append(self.create_measurement({'type':'general','metric':'ratio_in_quorum'},{'value':percentage}))

		return	points

