#ceph-influxDB-metricsCollector
By Ignacy Debicki

######This is a script to collect data about ceph and send it to influxDB >= v0.9.x

######Recommended python version of >=2.7
######Has been tested and works correctly on verison 2.6.6, however, optimisations in the json module are not implemented, so parsing json files takes significantly longer. If using version 2.6.x, it is highly recommended to also install simplejson.



To run it has the following dependencies:

* [influxdb-python](https://github.com/influxdb/influxdb-python)
  * [Requests](http://docs.python-requests.org/)

Optional libraries for 2.6.x to speed up JSON processing:
* [simplejson](https://github.com/simplejson/simplejson)

Also please ensure python has these libraries:

* os	
* imp
* ConfigParser
* inspect
* logging
* sys
* traceback
* json
* collections
* functools
* gzip
* cStringIO
* time
* sys
* subprocess
* argparse (if python version >= 2.7.x)
* optparse (if python version <= 2.6.x)

######Furthermore, you will require a ceph keychain on the machine this script will be running on.

##Installation & configuration:

1. Download this repository wherever you want to have it.
2. Configure the default settings you would like to use if reading a config file fails using the single `default.conf` config file
3. Copy `default.conf` to `/etc/ceph-influxDB-metricsCollector.conf`, and configure your normal configuration.
4. Make sure the user the scripts are going to be ran by can write in the desired log location.
5. Schedual the loader.py to run at your desired interval by creating a CRON job. For testing, you can just run plugins/./runLoop.py, which will run the scripts at the start of every minute. For one time runs, you can use plugins/./loader.py


###Defining alternative config file:

You can define an alternative config file by using `plugins/./loader.py -c path/to/config` or `plugins/./runLoop.py -c path/to/config`
Option `--config path/to/config` can also be used.

###Defining different intervals for runLoop.py:

You can define a different minute interval by using `plugins/./runLoop.py -i intervalInMinutes`
Option `—interval` may also be used

##Hotswapping plugins:

You can switch plugins whilst the program is running by turning them off or on in the configuration file.
If altering or changing the code of a plugin please remember to delete its corresponding .pyc file.

##Documentation:

The documentation folder contains some useful information about the way items are tagged, and a spreadsheet showing the sources of all metrics with a small calculator which estimates the number of points that are gathered with each run.

##Creating plugins:

All plugin classes must inherit from `base.Base` and implement the function `gather_metrics()`, which will return an array of all the measurements
To log events in your plugin, use `self.logger.` followed by the logging level this should show up under as defined by the logging library
e.g. `self.logger.info('Gathering metrics')`

Please see example.py for an example plugin structure.

To call commands use the function `self.execute_command(isJson,*args)` as the results of these operations are memoized, so multiple plugins calling and parsing the same command is not as resource intensive.
e.g. `self.execute_command(True,'ceph','osd','tree','--format','json')`
if `isJson = True`, the command will return a python dictionary from the parsed JSON. 

If parsing a JSON which is not retrived from a command, please use `self.readJson(jsonFile)`, as the result will be memoized.

To encode a measurement into a point, use `self.create_measurement(tags,fields)`
The built in methods, of escaping data can slow the system significantly when processing a large amount of points (~1 second extra per 100,000 points).
Due to this, they are commented out in influxLineProtocol.py, however can be commented back in if you require this functionality.
######Furthermore, please make sure your passed in values for fields can be formatted as floats.

N.B. when testing plugins and the source code is changed, but the change is not reflected when running it, please delete the script's corresponding .pyc file.

To enable the plugin, just add into the config file under plugins:
`pluginName=[ceph-cluster]`
