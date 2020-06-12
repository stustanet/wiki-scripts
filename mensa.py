#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import html
import sys
import urllib.request
from datetime import date

import mwclient
from bs4 import BeautifulSoup


def main():
    config = configparser.RawConfigParser()
    config.read('mensa.ini')
    cfg = config.get

    speisen = {}

    proxy_handler = urllib.request.ProxyHandler(
        {'http': cfg('mensa', 'proxy')})
    opener = urllib.request.build_opener(proxy_handler)
    page = opener.open(cfg('mensa', 'url')).read()
    soup = BeautifulSoup(page, 'html.parser')

    try:
        today = soup.find(attrs={'class': 'heute_' + date.today().strftime(
            '%Y_%m_%d') + '  anker'}).findPrevious(attrs={'class': 'menu'})
        rows = today.findAll('tr')
        for row in rows:
            gericht = row.findAll('span', attrs={'class': 'stwm-artname'})
            beschreibung = row.findAll('span')
            if gericht and beschreibung:
                gericht = gericht[0].string
                beschreibung = beschreibung[1].string
                speisen[gericht] = beschreibung
    except Exception as ex:
        print(ex)
        speisen = None

    site = mwclient.Site(cfg(
        'mwclient', 'site'), path=cfg('mwclient', 'path'))
    site.login(cfg('mwclient', 'user'), cfg('mwclient', 'pass'))

    page = site.Pages['Vorlage:Mensa-Heute']

    text = ''
    if speisen:
        for speise in speisen:
            text = text + '%s: %s' % (html.escape(speise),
                                      html.escape(speisen[speise]))
            text = text + '<br />\n'
    else:
        text = text + 'Heute nix\n'

    page.save(text, summary='Mensa Essen ' + date.today().strftime('%Y-%m-%d'))


if __name__ == '__main__':
    sys.exit(main())
