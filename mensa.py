#! /usr/bin/env python2
# -*- coding: utf-8 -*-

import mwclient, ConfigParser
import urllib2
import cgi
from datetime import date
from BeautifulSoup import BeautifulSoup

config = ConfigParser.RawConfigParser()
config.read('mensa.ini')
cfg = config.get


speisen = {}

proxy_handler = urllib2.ProxyHandler({'http': cfg('mensa', 'proxy')})
opener = urllib2.build_opener(proxy_handler)
f = opener.open(cfg('mensa', 'url'))

page = f.read()
# hack to make python parser happy
page = page.replace("</scri'+'pt>","</script>")

a = BeautifulSoup(page)

try:
    today = a.find(attrs={'class' : 'heute_' + date.today().strftime('%Y-%m-%d') + ' anker'}).findPrevious(attrs={'class': 'menu'})
    b = today.findAll('tr')
    for x in b:
        gericht = x.findAll('span', attrs={'class': 'stwm-artname'})
        beschreibung = x.findAll('span')
        if gericht and beschreibung:
            gericht = gericht[0].string
            beschreibung = beschreibung[1].string
            speisen[gericht] = beschreibung
except:
    speisen = None


site = mwclient.Site((cfg('mwclient', 'schema'), cfg('mwclient', 'site')), path=cfg('mwclient', 'path'))
site.login(cfg('mwclient', 'user'), cfg('mwclient', 'pass'))

page = site.Pages['Vorlage:Mensa-Heute']

text = ''
if speisen:
    for x in speisen:
        text = text + '%s: %s' % (cgi.escape(x), cgi.escape(speisen[x]))
        text = text + '<br />\n'
else:
    text = text + 'Heute nix\n'

page.save(text, summary = 'Mensa Essen ' + date.today().strftime('%Y-%m-%d'))

