import collections

def createLineProtocolBatch(measurements):
	'''
	Makes a correctly formatted batch of points in accordance with the line protocol, from an array of measurements in the format
	{measurement:measurementName, tags:{},fields:{},timestamp:12345678}
	Currently not being used
	'''
	batch = ''
	for m in measurements:
		batch = []
		append = batch.append
		try:
			#see if it contains timestamp
			append(createLineProtocolStatement(m['measurement'],m['tags'],m['fields'],m['timestamp']))
		except:
			append(createLineProtocolStatement(m['measurement'],m['tags'],m['fields']))

	#send to line protocol port
	return '\n'.join(batch)


def createLineProtocolStatement(measurement,tags,valuesToWrite,timestamp=''):
	'''
	Formats the data into the line protocol
	returns a string in accordance to the line protocol
	'''
	#These escape the values and measurements. They have been commented out as they cause 3+ extra seconds
	#of execution time overall but do not actually change any values if values passed in are correctly constructed
	'''
	measurement = escapeCharacters(measurement)
	valuesToWrite = escapeValueDict(valuesToWrite)
	'''
	#insert measurment string
	protocolArray = [measurement]

	
	if len(tags) > 0:
		#Escape values ignored until a good solution is found
		'''
		tags = escapeTagDict(tags)
		'''
		#sort according to golang - reduces strain on server
		tags = orderTags(tags)
		#format string correctly
		protocolArray.append('')
		protocolArray.append(getTagStrings(tags))


	#insert values
	protocolArray.append(getValueStrings(valuesToWrite))

	#insert timestamp
	if timestamp != '':
		protocolArray.append(' ')
		protocolArray.append(str(timestamp))

	return ''.join(protocolArray)

def getValueStrings(fields):
	'''
	Creates the fields part of the line protocol
	Formats a dictionary rntry of fields to the correct format:
	string --> "string"
	4 --> 4
	returns string
	'''
	fieldsArray = []
	for k,v in fields.iteritems():
		field = [k,'=']
		try:
			field.append(str(float(v)))
		except ValueError:
			#if not a number, add quotes
			field.extend(['"',v,'"'])
		fieldsArray.append(''.join(field))
	return ','.join(fieldsArray)

def getTagStrings(tags):
	'''
	Formats the dictionary entry of tags to the correct line protocol format
	returns string
	'''
	tagsArray=['']

	for k,v in tags.iteritems():
		#format key value pairs of tags
		tagStrings=[',',k,'=',str(v)]
		tagsArray.append(''.join(tagStrings))
	#add space between tags and value
	tagsArray.append(' ')
	return ''.join(tagsArray)

def orderTags(d):
	'''
	Orders the tags in lexicographical order. This reduces the strain on the database.
	returns ordered dictionary
	'''
	#order the tags into an ordered dictionary
	od = collections.OrderedDict(sorted(d.items()))
	return od

def escapeTagDict(d):
	'''
	Escapes all of the keys and value of tags listed in the tags dictionary
	returns dictionary
	'''
	#declare new dictionary to put the escaped tags in
	nd={}
	for k,v in d.iteritems():
		#escape each key-value pair
		k = escapeCharacters(k)
		v = escapeCharacters(v)
		nd[k]=v
	return nd

def escapeValueDict(d):
	'''
	Escapes illegal characters in field values and their keys. See influxDB for more information
	returns dictionary
	'''
	#declare new dictionary to put the escaped fields in
	nd={}
	for k,v in d.iteritems():
		#escape each key-value pair
		k = escapeCharacters(k)
		v = escapeValues(v)
		nd[k]=v
	return nd


def escapeValues(s):
	'''
	Escapes illegal characters in field values. See influxDB for more information
	returns string
	'''
	try:
		return s.replace('"','\\\"')
	except:
		#if cannot replace means it is a number or float. Ignore exception. No need to format
		return s

def escapeCharacters(s):
	'''
	Escapes illegal characters in tag values, tag keys and measurements. See influxDB for more information
	returns string
	'''
	try:
		s = s.replace(' ', '\ ')
		s = s.replace(',','\,')
		s= s.replace('=','\=')
	except:
		pass
	return s
