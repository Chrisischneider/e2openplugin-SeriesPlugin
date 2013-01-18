# by betonme @2012

from collections import defaultdict

from thread import start_new_thread

#Twisted 12.x
#from twisted.web.client import getPage as twGetPage
#Twisted 8.x
from twisted.web.client import _parse, HTTPClientFactory
from twisted.internet import reactor
from twisted.python.failure import Failure

from Tools.BoundFunction import boundFunction

# Internal
from ModuleBase import ModuleBase
from Helper import Cacher, Retry, INTER_QUERY_TIME


class IdentifierBase(ModuleBase, Cacher, Retry):
	def __init__(self):
		ModuleBase.__init__(self)
		Cacher.__init__(self)
		Retry.__init__(self)
		self.callback = None
		self.name = ""
		self.begin = None
		self.end = None
		self.channel = ""
		self.ids = []

	################################################
	# Twisted functions
	def getPage(self, callback, url, expires=INTER_QUERY_TIME):
		print "SSBase getPage"
		print url
		
		cached = self.getCached(url, expires)
		if cached:
			print "SSBase cached"
			#start_new_thread(self.base_callback, (cached, callback, url))
			self.base_callback(cached, callback, url)
		
		else:
			print "SSBase not cached"
			try:
				#Twisted 12.x use
				#deferred = twGetPage(url, timeout = 5)
				#deferred.addCallback(self.base_callback, deferred, callback, url)
				#deferred.addErrback(self.base_errback, deferred, callback)
				#self.deferreds.append(deferred)
				#Twisted 8.x
				contextFactory = None
				scheme, host, port, path = _parse(url)
				factory = HTTPClientFactory(url, timeout=30)
				if scheme == 'https':
					from twisted.internet import ssl
					if contextFactory is None:
						extFactory = ssl.ClientContextFactory()
					connector = reactor.connectSSL(host, port, factory, contextFactory)
				else:
					connector = reactor.connectTCP(host, port, factory)
				deferred = factory.deferred
				deferred.addCallback(self.base_callback, callback, url)
				deferred.addErrback(self.base_errback, callback, url)
				
			except Exception, e:
				import os, sys, traceback
				print _("SeriesPlugin getPage exception ") + str(e)
				exc_type, exc_value, exc_traceback = sys.exc_info()
				traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stdout)
				self.cancel()
				callback()

	def base_callback(self, page, callback, url):
		try:
			data = callback( page )
			if data:
				self.doCache(url, data)
			
		except Exception, e:
			import os, sys, traceback
			print _("SeriesPlugin getPage exception ") + str(e)
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stdout)

	def base_errback(self, err, callback, url):
		print "errback", url
		if isinstance(err, Exception):
			print _("Twisted Exception:\n%s\n%s") % (err.type, err.value)
		elif isinstance(err, Failure):
			#TEST Later
			if self.retry(err.type, url):
				# TODO Attention there is no retry counter yet
				print "RETRY"
				self.getPage(callback, url)
			return
		elif err:
			print _("Twisted failed\n%s") % str(err)
		callback( None )

	def cancel(self):
		pass


	################################################
	# Service prototypes
	@classmethod
	def knowsElapsed(cls):
		# True: Service knows elapsed air dates
		# False: Service doesn't know elapsed air dates
		return False

	@classmethod
	def knowsToday(cls):
		# True: Service knows today air dates
		# False: Service doesn't know today air dates
		return False

	@classmethod
	def knowsFuture(cls):
		# True: Service knows future air dates
		# False: Service doesn't know future air dates
		return False

	def getEpisode(self, callback, name, begin, end, channel):
		# On Success: Return a single season, episode, title tuple
		# On Failure: Return a empty list or None
		callback( None )
