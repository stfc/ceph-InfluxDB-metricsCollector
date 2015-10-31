import base

class CephPluginOSDStates(base.Base):

	def __init__(self,cluster,cache,timestamp,c,k):
		#initialise
		base.Base.__init__(self,cluster,cache,timestamp,c,k)

	def gather_metrics(self):
		'''
		Subclassed method of base.py which is called by loader.py
		Returns array of points collected by the plugin
		'''
		self.logger.info('Gathering metrics')

		
		#get OSD hierarchy
		osdHierarchy =self.get_osd_hierarchy()
		#create array for points made
		points = []
		
		points.extend(self.get_storage_data(osdHierarchy))
		points.extend(self.get_state_data(osdHierarchy))
		points.extend(self.get_perf_data(osdHierarchy))
		return points

	def get_state_data(self,osdHierarchy):
		'''
		Collects state of the osds.
		Returns array of points, formatted into the format of the line protocol
		metrics collected:
			-state
		'''
		#run ceph command
		self.logger.info('Getting storage info')
		output = self.execute_command(True,'ceph','osd','dump','--format','json')

		if output == None:
			self.logger.error('No output recieved from "ceph osd dump --format json"')
			return []
		points=[]
		#get osd data
		for o in output['osds']:
			osdID=o['osd']
			osdParents = osdHierarchy[osdID]
			#from status and exists create the state measurement
			state = ''
			if o['up'] == 1:
				state = 'up+'
			else:
				state = 'down+'

			if o['in'] == 1:
				state+='in'
			else:
				state+='out'
			points.append(self.create_osd_measurement(osdParents['rack'],osdParents['host'],osdID,state,1))

		return points


	def get_perf_data(self,osdHierarchy):
		'''
		Collects performance data of the osds.
		Returns array of points, formatted into the format of the line protocol
		metrics collected:
			-apply_latency
			-commit_latency
		'''
		self.logger.info('Getting performance info')
		#get data from storage data from pg dump
		output = self.execute_command(True,'ceph','osd','perf','--format','json')

		if output == None or output == {}:
			self.logger.warning('No output recieved from "ceph osd perf --format json"')
			return []

		points =[]
		#get commit and apply latency
		root = output['osd_perf_infos']
		for osd in root:
			osdID=osd['id']
			osdParents = osdHierarchy[osdID]
			for stat,statValue in osd['perf_stats'].iteritems():
				points.append(self.create_osd_measurement(osdParents['rack'],osdParents['host'],osdID,stat,statValue))

		return points

	def get_storage_data(self,osdHierarchy):
		'''
		Collects storage data of the osds.
		Returns array of points, formatted into the format of the line protocol
		metrics collected:
			-kb
			-kb_used
			-kb_avail
			-utilization
		'''
		self.logger.info('Getting storage info')
		#get data from storage data from pg dump
		output = self.execute_command(True,'ceph','osd','df','--format','json')
		#Could use ceph osd df -f json
		#together with ceph osd perf -f json
		#to get same data

		if output == None or output == {}:
			self.logger.warning('No output recieved from "ceph osd df --format json"')
			return []

		points =[]
		statsToExtract=['kb','kb_used','kb_avail','utilization']
		root = output['nodes']
		for osd in root:
			osdID=osd['id']
			osdParents = osdHierarchy[osdID]
			for stat in statsToExtract:
				points.append(self.create_osd_measurement(osdParents['rack'],osdParents['host'],osdID,stat,osd[stat]))

		return points


	def get_osd_hierarchy(self):
		'''
		Converts flat hierarchical tree into osds with their respective hosts and racks in format:
		{osd:{rack:rackName,host:hostName}}
		If osd does not have parent, None is put in place
		returns dicitonary
		'''
		self.logger.info('Creating osd hierarchy')
		#run ceph command
		output = self.execute_command(True,'ceph','osd','tree','--format','json')

		if output == None:
			self.logger.warning('No output recieved from "ceph osd tree --format json"')
			return []

		#extract the nodes dictionary from the base (root) dictionary
		nodes = output['nodes']
		#create empty dictionaries to populate
		rackChildren={}
		hostChildren={}
		unclaimedHosts={}
		unclaimedOSDs=[]
		osds={}

		#iterate through the flat nodes dictionary
		for o in nodes:
			#for each object in nodes
			if o['type']=='rack':
				#Register its children
				rackChildren[o['name']]=set(o['children'])

			elif o['type']=='host':
				#get list of children IDs
				children = o['children']
				#try to find parent in rackChildren
				parent = ''
				for p,s in rackChildren.iteritems():
					if o['id'] in s:
						#found parent
						parent = p
						#remove child from set of children of that rack
						s.remove(o['id'])
						if len(s)==0:
							#if rack is listing no more children, delete dictionary entry
							del rackChildren[p]
						break
				if parent == '':
					#add to unclaimed hosts (not a child of already iterated through racks)
					unclaimedHosts[o['name']]=set(children)
				#Register as not having all its children inserted. the entry is in the form rack.host:set(childrenToFind)
				hostChildren[parent+'.'+o['name']]=set(children)
				
			elif o['type']=='osd':
				#find parent in hostChildren
				foundClaimedParent = False
				for p,s in hostChildren.iteritems():
					if o['id'] in s:
						
						#found parent
						parent = p
						#get current location in tree of parent
						pathToParent = p.split('.')
						if not pathToParent[0]=='':
							foundClaimedParent = True
							#save rack and host of OSD
							osds[o['id']]={'rack':pathToParent[0],'host':pathToParent[1]}
							#remove child from set
							s.remove(o['id'])
							if len(s)==0:
								#if host is listing no more children, delete dictionary entry
								del hostChildren[p]
						
						break
				if not foundClaimedParent:
					#add to unclaimed OSDs (not a child of already iterated through hosts)
					unclaimedOSDs.append(o['id'])
			else:
				#ignore any other entries
				pass

		#sort hosts that dont have parents
		for k,c in unclaimedHosts.iteritems():
			#for each unclaimed host, get the name (k) and the set of children (c)
			for p,s in rackChildren.iteritems():
				#check if the name of the unclaimed host is being searched for by a rack
				if k in s:
					#remove child from set
					s.remove(k)
					if len(s)==0:
						#if rack is listing no more children, delete dictionary entry
						del rackChildren[p]
					
					#if host was looking for children, change its dictionary entry so that children can find it in its new location in the tree
					del hostChildren['.'+k]
					if len(children)>0:
						hostChildren[p+'.'+k]=c
					break

		#sort OSDs that don't have parents
		for i in unclaimedOSDs:
			#for each unclaimed OSD, get the id (i) 
			found = False
			for p,s in hostChildren.iteritems():
				if i in s:
					found = True
					#parent found. Extract path to parent
					pathToParent = p.split('.')
					if pathToParent[0]=='':
						#parent is not claimed
						pathToParent='None'
								
					else:
						#remove child from set
						s.remove(k)
						if len(s)==0:
							#if host is listing no more children, delete dictionary entry
							del hostChildren[p]

					#save rack and host of OSD
					osds[i]={'rack':pathToParent[0],'host':pathToParent[1]}
					break
			#no parent found
			if not found:
				#save rack and host of OSD
				osds[i]={'rack':'None','host':'None'}
		#return hierarchy
		self.logger.debug('Created hierarchy: "{0}"'.format(osds))
		return osds

	def create_osd_measurement(self,rack,host,osd,metric,value):

		#create tags and values dictionary
		tags = {'type':'osd','rack':str(rack),'host':str(host),'osd':str(osd),'metric':metric}
		fields = {'value':value}
		#return created measurement
		return self.create_measurement(tags,fields)
