#!/usr/bin/env python
# Posts semantic mediawiki news entries via NNTP.  To be run with minimal
# privileges shortly after every full hour

# Initial version, 10/2010:
#     B. Hof <hof@stusta.net>
# Made a little bit less unbelievably insane, 04/2012:
#     B. Braun <benjamin.braun@stusta.net>,
#     T. Klenze <tobias.klenze@stusta.net>
# Fixed stuff, 06/2016:
#     J. Schmidt <js@stusta.net>

import mwclient
from BeautifulSoup import BeautifulSoup

import smtplib
from email.mime.text import MIMEText
from email.Utils import formatdate
from email.header import Header

import re
import shutil
import string
import sys
import time
import urllib
from tempfile import NamedTemporaryFile
from nntplib import NNTP

# helper for line wrapping
def wrap(text, width):
    return reduce(lambda line, word, width=width: '%s%s%s' %
                  (line,
                   ' \n'[(len(line)-line.rfind('\n')-1
                         + len(word.split('\n',1)[0]
                              ) >= width)],
                   word),
                  text.split(' ')
                 )


# scrape news content
def scrape(site, path):
    c = {} # return dictionary object
    page = site.Pages[path.name]

    content = page.text()
    content = content.replace("{{!}}", "")
    content = content.split("\n}}\n")

    # set default values since they are not enforced by mw
    c['postdate'] = time.gmtime()
    c['author'] = "Infoseite"
    c['summary'] = ""

    c['isdate'] = False # In case this is also a "Termin"
    c['startdate'] = ""
    c['enddate'] = ""
    c['location'] = ""
    c['isssn'] = False # Will be set to true if it is posted to the StuStaNet section
    c['isnews'] = False # Will be set to trueif it is posted to the general news section

    c['displaytitle'] = path.name.encode('utf-8') # Ommits index at the end (Adminrat im April 2 -> Adminrat im April) 
    c['title'] = path.normalize_title(path.name).encode('utf-8') # URL encoded

    for item in content:
        if item.startswith("{{StuStaNet-News"):
            c['isssn'] = True
        if item.startswith("{{News"):
            c['isnews'] = True
        if re.search("^{{.*News\n", item):
            item = item.strip()
            news = item.split("\n|")

            for record in news[1:]:
                name, value = record.split("=")
                if name == "Datum":
                    c['postdate'] = time.strptime(value, "%Y/%m/%d %H:%M:%S")
                if name == "Titel":
                    c['displaytitle'] = value
                if name == "Autor":
                    c['author'] = value
                if name == "auf Infoseite":
                    c['isnews'] = value;
                if name == "Zusammenfassung":
                    c['summary'] = ''.join(BeautifulSoup(value).findAll(text=True)).strip()
                    c['summary'] = wrap(c['summary'], 72)

        if item.find("{{Termin") != -1:
            item = item.strip()
            dates = item.splitlines()
            if dates[1].find("|Titel=") == 0:
                i = 1
            else:
                i = 0
            c['startdate'] = dates[i+1].split('=')[1]
            c['enddate'] = dates[i+2].split('=')[1]
            # location optional
            if len(dates) > i + 4:
                loc = dates[i+4].split('=')
                if len(loc) > 1:
                    c['location'] = loc[1]
            c['isdate'] = True

    if len(content) > 1:
        html = content[len(content) - 1]
    else:
        html = ""
    c['text'] = ''.join(BeautifulSoup(html).findAll(text=True)).strip()
    c['text'] = wrap(c['text'], 72)

    for key, value in c.iteritems():
        if key != 'text' and key != 'postdate' and key != 'summary' and key!= 'isdate' and key!='isssn' and key!='isnews':
            tmp = c[key]
            c[key] = c[key].replace("\n", "")
            c[key] = c[key].replace("\r", "")
            if (c[key] != tmp):
                print "WARNING: IT IS POSSIBLE THAT SOMEONE TRIED SOMETHING NASTY! Replaced " + tmp + " by " + c[key]

    return c


# write body of posting to tmpfile
def write_body(c):
    tmp = NamedTemporaryFile(mode='w+b')
    tmp.write("Zusammenfassung:\n")
    tmp.write(c['summary'].encode('utf-8'))
    if c['isdate']:
        tmp.write("\n")
        tmp.write("\n")
        tmp.write(c['startdate'].encode('utf-8'))
        tmp.write(" bis ")
        tmp.write(c['enddate'].encode('utf-8'))
        tmp.write("\n")
        tmp.write(c['location'].encode('utf-8'))
    tmp.write("\n\n")
    tmp.write(c['text'].encode('utf-8'))
    tmp.write("\n\n\n")
    tmp.write("Quelle: https://wiki.stusta.de/" \
            + urllib.quote_plus(c['title']))
    tmp.write("\n\n-- \nMehr Informationen: https://info.stusta.de\n")
    return tmp


# write ng header
def write_ng(c):
    tmp = NamedTemporaryFile(mode='w+b')
    headerfrom = Header(c['author'],"utf-8",76,"From")
    headerfrom.append("<no-reply@stusta.de>","ascii")
    tmp.write("From: " + headerfrom.encode() + "\n")
    tmp.write("Subject: " + Header(c['displaytitle'],"utf-8",76,"Subject").encode() + "\n")

    if (c['isssn'] and c['isnews']) :
        tmp.write("Newsgroups: local.netz.info,local.ankuendigungen\n")
    if (c['isssn'] and not c['isnews']):
        tmp.write("Newsgroups: local.netz.info\n")
    if (not c['isssn'] and c['isnews']):
        tmp.write("Newsgroups: local.ankuendigungen\n")
    if (not c['isssn'] and not c['isnews']):
        print "Well, this is kinda strange... it should never happen \
        that we dont post to either newsgroup:)"

    #tmp.write("Newsgroups: local.test\n")

    tmp.write("X-Newsreader: mw2nntp.py by StuStaNet nntp fan club\n")
    tmp.write("Content-Type: text/plain; charset=UTF-8\n")
    tmp.write("Content-Transfer-Encoding: 8bit\n")
    tmp.write("\n")
    return tmp


# dispatch posting to ng server
def send_ng(f):
    s = NNTP('news.stusta.de')
    #s.set_debuglevel(1)
    f.seek(0)
    try:
        s.post(f)
    except:
        print "Unexpected error:", sys.exc_info()[0]
    s.quit()
    f.close()


# send mail to, admin list
def send_mail(c, body):
    if not c['isssn']:
        return

    src = c['author'] + " <no-reply@mail.stusta.de>"

    dest = "announce@lists.stusta.de"

    body.seek(0)
    msg = MIMEText(body.read(), _charset="UTF-8")
    msg['Subject'] = c['displaytitle']
    msg['From'] = src
    msg['To'] = dest
    msg['Date']    = formatdate(localtime=True)
    s = smtplib.SMTP('mail.stusta.de')
    s.sendmail(src, [dest], msg.as_string())
    s.quit()


def main(argv=sys.argv):
    # collect pages
    site = mwclient.Site('wiki.stusta.de', path='/')

    categories = []
    categories.append(site.Pages['Kategorie:News'])
    categories.append(site.Pages['Kategorie:StuStaNet-News'])

    pages = {}

    for category in categories:
        for page in category:
            pages[page.name] = page

    interval = 60*60
    curtime = int(time.time() - interval)
    for (pagetitle,page) in pages.iteritems(): # "guranteed" to be unique
        c = scrape(site, page)
        # dispatch news to ng if posted during previous full hour
        newstime = int(time.mktime(c['postdate']))
        if int(curtime / interval) == int(newstime / interval):
            body = write_body(c)
            send_mail(c, body)

            # create ng header and append text
            posting = write_ng(c)
            body.seek(0)
            shutil.copyfileobj(body, posting)
            send_ng(posting)

if __name__ == '__main__':
    sys.exit(main())
