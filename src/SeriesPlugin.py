# by betonme @2012

import re
import os, sys, traceback
from time import gmtime, strftime
from datetime import datetime

# Localization
from . import _

from datetime import datetime

from Components.config import config

from enigma import eServiceReference, iServiceInformation, eServiceCenter, ePythonMessagePump
from ServiceReference import ServiceReference

# Plugin framework
from Modules import Modules

# Tools
from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Tools.Notifications import AddPopup
from Screens.MessageBox import MessageBox

# Plugin internal
from IdentifierBase import IdentifierBase
from ManagerBase import ManagerBase
from GuideBase import GuideBase
from Channels import ChannelsBase, removeEpisodeInfo, lookupServiceAlternatives
from Logger import splog

#from CancelableThread import QueueWithTimeOut, CancelableThread, synchronized, myLock
#from Queue import Queue, Empty
#from threading import Thread, Event

#from threading import Lock


# Constants
IDENTIFIER_PATH = os.path.join( resolveFilename(SCOPE_PLUGINS), "Extensions/SeriesPlugin/Identifiers/" )
MANAGER_PATH    = os.path.join( resolveFilename(SCOPE_PLUGINS), "Extensions/SeriesPlugin/Managers/" )
GUIDE_PATH      = os.path.join( resolveFilename(SCOPE_PLUGINS), "Extensions/SeriesPlugin/Guides/" )


# Globals
instance = None

CompiledRegexpNonDecimal = re.compile(r'[^\d]+')


def getInstance():
	global instance
	#if instance is None:
	from plugin import VERSION
	splog("SERIESPLUGIN NEW INSTANCE " + VERSION)
	try:
		for key, value in config.plugins.seriesplugin.dict().iteritems():
			splog( "config.plugins.seriesplugin.%s = %s" % (key, value) )
	except Exception, e:
		pass
	instance = SeriesPlugin()
	#instance[os.getpid()] = SeriesPlugin()
	splog( strftime("%a, %d %b %Y %H:%M:%S", gmtime()) )
	return instance

def resetInstance():
	#Rename to closeInstance
	global instance
	if instance is not None:
		splog("SERIESPLUGIN INSTANCE STOP")
		instance.stop()
		instance = None
	from Cacher import cache
	global cache
	cache = {}


def refactorTitle(org, data):
	if data:
		season, episode, title, series = data
		if config.plugins.seriesplugin.pattern_title.value and not config.plugins.seriesplugin.pattern_title.value == "Off":
			#if season == 0 and episode == 0:
			#	return config.plugins.seriesplugin.pattern_title.value.strip().format( **{'org': org, 'title': title, 'series': series} )
			#else:
			return config.plugins.seriesplugin.pattern_title.value.strip().format( **{'org': org, 'season': season, 'episode': episode, 'title': title, 'series': series} )
		else:
			return org
	else:
		return org

def refactorDescription(org, data):
	if data:
		season, episode, title, series = data
		if config.plugins.seriesplugin.pattern_description.value and not config.plugins.seriesplugin.pattern_description.value == "Off":
			#if season == 0 and episode == 0:
			#	description = config.plugins.seriesplugin.pattern_description.value.strip().format( **{'org': org, 'title': title, 'series': series} )
			#else:
			description = config.plugins.seriesplugin.pattern_description.value.strip().format( **{'org': org, 'season': season, 'episode': episode, 'title': title, 'series': series} )
			description = description.replace("\n", " ")
			return description
		else:
			return org
	else:
		return org


class SeriesPlugin(Modules, ChannelsBase):
	def __init__(self):
		splog("SeriesPlugin")
		Modules.__init__(self)
		ChannelsBase.__init__(self)
		
		self.serviceHandler = eServiceCenter.getInstance()
		
		#http://bugs.python.org/issue7980
		datetime.strptime('2012-01-01', '%Y-%m-%d')
		
		self.identifiers = self.loadModules(IDENTIFIER_PATH, IdentifierBase)
		
		self.identifier_elapsed = self.instantiateModuleWithName( self.identifiers, config.plugins.seriesplugin.identifier_elapsed.value )
		splog(self.identifier_elapsed)
		
		self.identifier_today = self.instantiateModuleWithName( self.identifiers, config.plugins.seriesplugin.identifier_today.value )
		splog(self.identifier_today)
		
		self.identifier_future = self.instantiateModuleWithName( self.identifiers, config.plugins.seriesplugin.identifier_future.value )
		splog(self.identifier_future)

	def stop(self):
		splog("SeriesPluginWorker stop")
		if config.plugins.seriesplugin.lookup_counter.isChanged():
			config.plugins.seriesplugin.lookup_counter.save()
		self.saveXML()
	
	################################################
	# Identifier functions
	def getIdentifier(self, future=False, today=False, elapsed=False):
		if elapsed:
			return self.identifier_elapsed and self.identifier_elapsed.getName()
		elif today:
			return self.identifier_today and self.identifier_today.getName()
		elif future:
			return self.identifier_future and self.identifier_future.getName()
		else:
			return None
	
	def getEpisode(self, callback, name, begin, end=None, service=None, future=False, today=False, elapsed=False):
		#available = False
		
		name = removeEpisodeInfo(name)
		begin = datetime.fromtimestamp(begin)
		end = datetime.fromtimestamp(end)
		
		#MAYBE for all valid identifier in identifiers:
		
		# Return a season, episode, title tuple
		
		if elapsed:
			identifier = self.identifier_elapsed
		elif today:
			identifier = self.identifier_today
		elif future:
			identifier = self.identifier_future
		else:
			identifier = None
		
		if identifier:
			try:
				
				channels = lookupServiceAlternatives(service)
				
				result = identifier.getEpisode(
								name, begin, end, service, channels
							)
				
				if result and len(result) == 4:
				
					season, episode, title, series = result
					season = int(CompiledRegexpNonDecimal.sub('', season))
					episode = int(CompiledRegexpNonDecimal.sub('', episode))
					title = title.strip()
					splog("SeriesPluginWorkerThread result callback")
					callback( (season, episode, title, series) )
					
					config.plugins.seriesplugin.lookup_counter.value += 1
					config.plugins.seriesplugin.lookup_counter.save()
					
				else:
					splog("SeriesPluginWorkerThread result failed")
					callback( result )
					
			except Exception, e:
				splog("SeriesPluginWorkerThread Callback Exception:", str(e))
				callback( str(e) )
			
			
#TBD Because of E2 Update 05.2013
		#from threading import currentThread
		#if currentThread().getName() == 'MainThread':
#			if (config.plugins.seriesplugin.lookup_counter.value == 10) \
#				or (config.plugins.seriesplugin.lookup_counter.value == 100) \
#				or (config.plugins.seriesplugin.lookup_counter.value % 1000 == 0):
#				from plugin import ABOUT
#				about = ABOUT.format( **{'lookups': config.plugins.seriesplugin.lookup_counter.value} )
#				AddPopup(
#					about,
#					MessageBox.TYPE_INFO,
#					0,
#					'SP_PopUp_ID_About'
#				)
			
			return identifier.getName()
			
		#if not available:
		else:
			callback( "No identifier available" )
