#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import configparser
import json
import locale
import os
import sys
import urllib.request
from datetime import date
from datetime import datetime

import mwclient

WIKITEXT_DE = '''
|style="vertical-align:bottom;"| %s
|style="text-align:right;"| %s - %s Uhr
'''

WIKITEXT_EN = '''
|style="vertical-align:bottom;"| %s
|style="text-align:right;"| from %s to %s
'''

SPECIAL = {"\xc4": "Ä", "\xe4": "ä", "\xd6": "Ö",
           "\xf6": "ö", "\xdc": "ü", "\xfc": "ü", "\xdf": "ß"}


def convert_date(obj):
    obj['start'] = datetime.fromtimestamp(obj['start'])
    obj['end'] = datetime.fromtimestamp(obj['end'])
    return obj


def wikify_date(obj, wiki_text):
    text = (wiki_text % (obj['start'].strftime('%A, %d. %B %Y'), obj[
            'start'].strftime('%H:%M'), obj['end'].strftime('%H:%M')))
    for key, value in SPECIAL.items():
        text = text.replace(key, value)
    return text


def main():
    config = configparser.RawConfigParser()
    config.read(os.path.dirname(os.path.realpath(__file__)) + '/sss.ini')
    cfg = config.get

    opener = urllib.request.build_opener()
    page = opener.open(cfg('sss', 'url')).read()

    appointments = [convert_date(x) for x in json.loads(page)]

    site = mwclient.Site(cfg('mwclient', 'site'), path=cfg('mwclient', 'path'))
    site.login(cfg('mwclient', 'user'), cfg('mwclient', 'pass'))

    # deutsche version

    locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
    wiki_lines = [wikify_date(x, WIKITEXT_DE) for x in appointments]

    page = site.Pages['Vorlage:Sprechstunden']
    page.edit("{|" + "|-".join(wiki_lines) + "|}",
              summary='Sprechstunden ' + date.today().strftime('%Y-%m-%d'))

    # englische version

    locale.setlocale(locale.LC_TIME, "en_US.UTF-8")
    wiki_lines = [wikify_date(x, WIKITEXT_EN) for x in appointments]

    page = site.Pages['Vorlage:Sprechstunden/en']
    page.edit("{|" + "|-".join(wiki_lines) + "|}",
              summary='Sprechstunden ' + date.today().strftime('%Y-%m-%d'))


if __name__ == '__main__':
    sys.exit(main())
