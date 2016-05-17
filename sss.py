#! /usr/bin/env python2
# -*- coding: utf-8 -*-

import mwclient, ConfigParser
import urllib2
import cgi
from datetime import datetime
from datetime import date
import json
import locale

wikiText_de = '''
|style="vertical-align:bottom;"| %s
|style="text-align:right;"| %s - %s Uhr
''' 

wikiText_en = '''
|style="vertical-align:bottom;"| %s
|style="text-align:right;"| from %s to %s 
'''

special = {"\xc4": "Ä", "\xe4": "ä", "\xd6" : "Ö", "\xf6" : "ö", "\xdc" : "ü", "\xfc" : "ü", "\xdf" : "ß"} 

def convertDate(obj):
	obj['start'] = datetime.fromtimestamp(obj['start'])
	obj['end'] = datetime.fromtimestamp(obj['end'])
	return obj

def wikifyDate(obj, wikiText):
	text = (wikiText % (obj['start'].strftime('%A, %d. %B %Y'), obj['start'].strftime('%H:%M'), obj['end'].strftime('%H:%M')))
	for key in special.keys(): 
		text = text.replace(key, special[key]) 	
	return text

config = ConfigParser.RawConfigParser()
config.read('sss.ini')
cfg = config.get

opener = urllib2.build_opener()
f = opener.open(cfg('sss', 'url'))

page = f.read()

appointments = [convertDate(x) for x in json.loads(page)]

site = mwclient.Site((cfg('mwclient', 'schema'), cfg('mwclient', 'site')), path=cfg('mwclient', 'path'))
site.login(cfg('mwclient', 'user'), cfg('mwclient', 'pass'))

# deutsche version

locale.setlocale(locale.LC_TIME, "de_DE")
wikiLines = [wikifyDate(x, wikiText_de) for x in appointments]

page = site.Pages['Vorlage:Sprechstunden']
page.edit()

page.save("{|" + "|-".join(wikiLines) + "|}" , summary = 'Sprechstunden ' + date.today().strftime('%Y-%m-%d'))

# englische version

locale.setlocale(locale.LC_TIME, "en_US")
wikiLines = [wikifyDate(x, wikiText_en) for x in appointments]

page = site.Pages['Vorlage:Sprechstunden/en']
page.edit()

page.save("{|" + "|-".join(wikiLines) + "|}" , summary = 'Sprechstunden ' + date.today().strftime('%Y-%m-%d'))
