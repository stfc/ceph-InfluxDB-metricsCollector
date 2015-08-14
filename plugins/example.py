import base

class SomePlugin(base.Base):
	def __init__(self,cluster,cache,timestamp,c,k):
		#initialise
		base.Base.__init__(self,cluster,cache,timestamp,c,k)

	def gather_metrics(self):
		'''
		Subclassed method of base.py which is called by loader.py
		Returns array of points collected by the plugin
		'''
		self.logger.info('Gathering metrics')
		#run ceph command
		output = self.execute_command(True,'ceph','osd','tree','--format','json')

		if output == None:
			self.logger.warning('No output recieved from "ceph osd tree --format json"')
			return []

		points = []

		#Process data here to create points
		#points.append(self.create_measurement({tags},{fields}))

		return points