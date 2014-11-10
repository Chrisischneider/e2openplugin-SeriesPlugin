# by betonme @2012

# Imports
from Components.config import config

from Tools.BoundFunction import boundFunction

from urllib import urlencode

from HTMLParser import HTMLParser

from datetime import datetime

import re
from sys import maxint

# Internal
from Plugins.Extensions.SeriesPlugin.IdentifierBase import IdentifierBase
from Plugins.Extensions.SeriesPlugin.Channels import compareChannels
from Plugins.Extensions.SeriesPlugin.Logger import splog

from iso8601 import parse_date

# Constants
SERIESLISTURL     = "http://www.wunschliste.de/ajax/search_dropdown.pl?"
EPISODEIDURLATOM  = "http://www.wunschliste.de/xml/atom.pl?"
#EPISODEIDURLRSS  = "http://www.wunschliste.de/xml/rss.pl?"

# Series: EpisodeTitle (Season.Episode) - Weekday Date, Time / Channel (Country)
# Two and a Half Men: Der Mittwochs-Mann (1.5) - Mi 02.05., 19.50:00 Uhr / TNT Serie (Pay-TV)
# Two and a Half Men: Der Mittwochs-Mann (1.5) - Mi 02.05., 19.50:00 Uhr / TNT Serie
# Two and a Half Men: Der Mittwochs-Mann (1) (1.5) - Mi 02.05., 19.50:00 Uhr / TNT Serie
# Der Troedeltrupp - Das Geld liegt im Keller: Folge 109 (109) - Do 03.05., 16.15:00 Uhr / RTL II
# Galileo: U.a.: Die schaerfste Chili der Welt - Fr 04.05., 19.05:00 Uhr / ProSieben
# Galileo: Magazin mit Aiman Abdallah, BRD 2012 - Mi 09.05., 06.10:00 Uhr / ProSieben
# Gute Zeiten, schlechte Zeiten: Folgen 4985 - 4988 (21.84) - Sa 05.05., 11.00:00 Uhr / RTL
# Channel is between last / and ( or line end
CompiledRegexpAtomChannel = re.compile('\/(?!.*\/) ([^\(]+)')
# Date is between last - and channel
CompiledRegexpAtomDate = re.compile('-(?!.*-) (.+)')
# Find optional episode
CompiledRegexpAtomEpisode = re.compile('\((?!.*\()(.+)\) ')
# Series: Title
CompiledRegexpAtomTitle = re.compile('.+: (.+)')

# (Season.Episode) - EpisodeTitle
# (21.84) Folge 4985
# (105) Folge 105
# (4.11/4.11) Mama ist die Beste/Rund um die Uhr
# Galileo: Die schaerfste Chili der Welt
# Galileo: Jumbo auf Achse: Muelltonnenkoch
# Gute Zeiten, schlechte Zeiten: Folgen 4985 - 4988 (21.84) - Sa 05.05., 11.00:00 Uhr / RTL
#CompiledRegexpPrintTitle = re.compile( '(\(.*\) )?(.+)')

CompiledRegexpEpisode = re.compile( '((\d+)[\.x])?(\d+)')


class WLAtomParser(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		self.title = False
		self.updated = False
		self.titlestr = ''
		self.updatedstr = ''
		self.list = []

	def handle_starttag(self, tag, attributes):
		if tag == 'title':
			self.title = True
		elif tag == 'updated':
			self.updated = True

	def handle_endtag(self, tag):
		if tag == 'title':
			self.title = False
		elif tag == 'updated':
			self.updated = False
		elif tag == 'entry':
			self.list.append( (self.titlestr, self.updatedstr) )
			self.titlestr = ''
			self.updatedstr = ''

	def handle_data(self, data):
		if self.title:
			self.titlestr += data
		elif self.updated:
			self.updatedstr = data


class WunschlisteFeed(IdentifierBase):
	def __init__(self):
		IdentifierBase.__init__(self)

	@classmethod
	def knowsToday(cls):
		return False

	@classmethod
	def knowsFuture(cls):
		return True

	def getEpisode(self, name, begin, end=None, service=None, channels=[]):
		# On Success: Return a single season, episode, title tuple
		# On Failure: Return a empty list or String or None
		
		self.begin = begin
		self.end = end
		self.service = service
		self.channels = channels
		
		self.returnvalue = None
		
		# Check preconditions
		if not name:
			splog(_("Skip Wunschliste: No show name specified"))
			return _("Skip Wunschliste: No show name specified")
		if not begin:
			splog(_("Skip Wunschliste: No begin timestamp specified"))
			return _("Skip Wunschliste: No begin timestamp specified")
		
		splog("WunschlisteFeed getEpisode")
		
		while name:	
			ids = self.getSeries(name)
			
			while ids:
				idserie = ids.pop()
				
				if idserie and len(idserie) == 2:
					id, self.series = idserie
					
					result = self.getNextPage( id )
					if result:
						return result
					
			else:
				name = self.getAlternativeSeries(name)
		
		else:
			return ( self.returnvalue or _("No matching series found") )

	def getSeries(self, name):
		url = SERIESLISTURL + urlencode({ 'q' : re.sub("[^a-zA-Z0-9-*]", " ", name) })
		data = self.getPage( url )
		
		if data and isinstance(data, basestring):
			data = self.parseSeries(data)
			self.doCache(url, data)
		
		if data and isinstance(data, list):
			splog("WunschlisteFeed ids", data)
			return data

	def parseSeries(self, data):
		serieslist = []
		for line in data.splitlines():
			values = line.split("|")
			if len(values) == 4:
				idname, countryyear, id, temp = values
				splog(id, idname)
				serieslist.append( (id, idname) )
			else:
				splog("WunschlisteFeed: ParseError: " + str(line))
		serieslist.reverse()
		return serieslist

	def parseNextPage(self, data):
		# Handle malformed HTML issues
		data = data.replace('&amp;','&')  # target=\"_blank\"&amp;
		parser = WLAtomParser()
		parser.feed(data)
		#splog(parser.list)
		return parser.list
	
	def getNextPage(self, id):
		splog("WunschlisteFeed getNextPage")
		
		url = EPISODEIDURLATOM + urlencode({ 's' : id })
		data = self.getPage( url )
		
		if data and isinstance(data, basestring):
			data = self.parseNextPage(data)
			self.doCache(url, data)
		
		if data and isinstance(data, list):
			trs = data
			
			yepisode = None
			ydelta = maxint
			
			for tds in trs:
				if tds and len(tds) == 2:
					xtitle, xupdated = tds
					if xtitle is not None and xupdated is not None:
						#import iso8601
						#http://code.google.com/p/pyiso8601/
						xbegin = parse_date(xupdated)
						xbegin = xbegin.replace(tzinfo=None)
						
						#"2014-11-10T20:15:00+01:00"
						#xbegin =  datetime.strptime(xupdated[0:-6], "%Y-%m-%dT%H:%M:%S");
						
						#Py2.6
						delta = abs(self.begin - xbegin)
						delta = delta.seconds + delta.days * 24 * 3600
						#Py2.7 delta = abs(self.begin - xbegin).total_seconds()
						splog(self.begin, xbegin, delta, int(config.plugins.seriesplugin.max_time_drift.value)*60)
						
						if delta <= int(config.plugins.seriesplugin.max_time_drift.value) * 60:
							result = CompiledRegexpAtomChannel.search(xtitle)
							if result and len(result.groups()) >= 1:
								
								if compareChannels(self.channels, result.group(1), self.service):
									
									if delta < ydelta:
										# Slice string to remove channel
										xtitle = xtitle[:result.start()]
										result = CompiledRegexpAtomDate.search(xtitle)
										
										if result and len(result.groups()) >= 1:
											# Slice string to remove date
											xtitle = xtitle[:result.start()]
											result = CompiledRegexpAtomEpisode.search(xtitle)
											
											if result and len(result.groups()) >= 1:
												# Extract season and episode
												xepisode = result.group(1)
												# Slice string to remove season and episode
												xtitle = xtitle[:result.start()]
												
												result = CompiledRegexpEpisode.search(xepisode)
												if result and len(result.groups()) >= 3:
													xseason = result and result.group(2) or "1"
													xepisode = result and result.group(3) or "0"
												else:
													splog("WunschlisteFeed wrong episode format", xepisode)
													xseason = "1"
													xepisode = "0"
											else:
												splog("WunschlisteFeed wrong title format", xtitle)
												xseason = "0"
												xepisode = "0"
											result = CompiledRegexpAtomTitle.search(xtitle)
											
											if result and len(result.groups()) >= 1:
												# Extract episode title
												xtitle = result.group(1)
												yepisode = (xseason, xepisode, xtitle.decode('ISO-8859-1').encode('utf8'), self.series.decode('ISO-8859-1').encode('utf8'))
												ydelta = delta
									
									else: #if delta >= ydelta:
										break
								
								else:
									self.returnvalue = _("Check the channel name")
								
						elif yepisode:
							break
			
			if yepisode:
				return ( yepisode )
