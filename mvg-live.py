#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
    SSN_MVG: MVV-Abfahrtszeiten an der Studentenstadt für die Infoseite
"""

import sys
import mwclient
import urllib
import lxml.html

anzahl = 8

# Fetch from mvg-live website
abfahrten = []
html = lxml.html.fromstring(urllib.urlopen('http://www.mvg-live.de/ims/dfiStaticAuswahl.svc?haltestelle=Studentenstadt', proxies={'http': 'http://proxy.stusta.mhn.de:3128'}).read().decode('iso8859-1'))
departureView = html.find_class('departureView')

# Exit if fetch failed
if len(departureView) < 1:
    exit(1)

# Extract info
table = departureView[0]
for row in  table.cssselect("tr"):
    if row.find_class('rowOdd') or row.find_class('rowEven'):
        line = row.find_class('lineColumn')[0].text_content()
        destination = row.find_class('stationColumn')[0].text_content().strip()
        minutes = row.find_class('inMinColumn')[0].text_content()
        abfahrten.append({'line':line, 'destination':destination,
            'minutes':minutes})
    elif row.find_class('serverTimeColumn'):
        time = row.find_class('serverTimeColumn')[0].text_content()

# Convert to wiki-syntax

# Sonderzeichen
special = {"\xc4": "Ä", "\xe4": "ä", "\xd6" : "Ö", "\xf6" : "ö", "\xdc" : "ü", "\xfc" : "ü", "\xdf" : "ß"}

wikistring = 'Stand: ' + time + '\n' +\
        '{|class="wikitable center"\n! Linie !! Ziel !! Abfahrt in\n|-\n'
for eintrag in abfahrten[0:anzahl]:
    if eintrag['line'].startswith('U'):
        wikistring = wikistring + \
                '|| [[Datei:Logo-U-Bahn.svg|frameless|20px]] ' +\
                    eintrag['line'] + '\n' + \
                '|| ' + eintrag['destination'] + '\n' +\
                '|| ' + str(eintrag['minutes']) + '\n' +\
                '|-\n'
    else:
        wikistring = wikistring + \
                '|| [[Datei:Logo-Bus.svg|frameless|20px]] ' +\
                    eintrag['line'] + '\n' + \
                '|| ' + eintrag['destination'] + '\n' +\
                '|| ' + str(eintrag['minutes']) + '\n' +\
                '|-\n'

wikistring = wikistring + '|}'

mw_user = 'Sprechstundensystem-Bot'
mw_pass = 'pgUeJ6jN3uZoncH[%B6x'

site = mwclient.Site('wiki.stusta.mhn.de', path='/')
site.login(mw_user, mw_pass)

page = site.Pages['Vorlage:MVV-Abfahrt']
page.edit()

page.save(wikistring , summary = 'MVV-Abfahrt' )
