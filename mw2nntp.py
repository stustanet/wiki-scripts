#!/usr/bin/env python
# B. Hof <hof@stusta.net>, 10/2010
# Posts semantic mediawiki news entries via NNTP.  To be run with minimal
# privileges shortly after every full hour

import mwclient
from BeautifulSoup import BeautifulSoup

import smtplib
from email.mime.text import MIMEText

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
    page = site.Pages[path.name]
    content = page.edit()
    content = content.replace("{{!}}", "")
    content = content.split("\n}}\n")

    # set default values since they are not enforced by mw
    postdate = time.localtime()
    author = "Infoseite"
    title = "Neuigkeiten"
    summary = ""

    date = False
    startdate = ""
    enddate = ""
    location = ""
    ssn = False
    for item in content:
        if item.startswith("{{StuStaNet-News"):
            ssn = True
        if re.search("^{{.*News\n", item):
            item = item.strip()
            news = item.split("\n|")

            for record in news[1:]:
                name, value = record.split("=")
                if name == "Datum":
                    postdate = time.strptime(value, "%Y/%m/%d %H:%M:%S")
                if name == "Titel":
                    title = value
                if name == "Autor":
                    author = value
                if name == "Zusammenfassung":
                    summary = ''.join(BeautifulSoup(value).findAll(text=True)).strip()
                    summary = wrap(summary, 72)

        if item.find("{{Termin") != -1:
            item = item.strip()
            date = item.splitlines()
            if date[1].find("|Titel=") == 0:
                i = 1
            else:
                i = 0
            startdate = date[i+1].split('=')[1]
            enddate = date[i+2].split('=')[1]
            # location optional
            if len(date) > i + 4:
                loc = date[i+4].split('=')
                if len(loc) > 1:
                    location = loc[1]
            date = True

    if len(content) > 1:
        html = content[len(content) - 1]
    else:
        html = ""
    text = ''.join(BeautifulSoup(html).findAll(text=True)).strip()
    text = wrap(text, 72)
    return (title, postdate, author, date, startdate, enddate, location, \
            summary, text, ssn)


# write body of posting to tmpfile
def write_body(content):
    tmp = NamedTemporaryFile(mode='w+b')
    tmp.write("Zusammenfassung:\n")
    tmp.write(content[7].encode('utf-8'))
    if content[3]:
        tmp.write("\n")
        tmp.write("\n")
        tmp.write(content[4].encode('utf-8'))
        tmp.write(" bis ")
        tmp.write(content[5].encode('utf-8'))
        tmp.write("\n")
        tmp.write(content[6].encode('utf-8'))
    tmp.write("\n\n")
    tmp.write(content[8].encode('utf-8'))
    tmp.write("\n\n\n")
    tmp.write("Quelle: https://wiki.stusta.mhn.de/Aktuelles:" \
            + urllib.quote_plus(content[0]))
    tmp.write("\n\n-- \nMehr Informationen: https://info.stusta.mhn.de\n")
    return tmp


# write ng header
def write_ng(content):
    tmp = NamedTemporaryFile(mode='w+b')
    tmp.write("From: " + content[2].encode('utf-8') + " <nobody@example.com>\n")
    title = content[0].encode('utf-8')
    tmp.write("Subject: " + title + "\n")
    if (content[9]) :
        tmp.write("Newsgroups: local.netz.info\n")
    else :
        tmp.write("Newsgroups: local.ankuendigungen\n")
    #tmp.write("Newsgroups: local.test\n")
    tmp.write("X-Newsreader: mw2nntp.py by StuStaNet nntp fan club\n")
    tmp.write("Content-Type: text/plain; charset=UTF-8\n")
    tmp.write("Content-Transfer-Encoding: 8bit\n")
    tmp.write("\n")
    return tmp


# dispatch posting to ng server
def send_ng(f):
    s = NNTP('news.stusta.mhn.de')
    #s.set_debuglevel(1)
    f.seek(0)
    try:
        s.post(f)
    except:
        print "Unexpected error:", sys.exc_info()[0]
    s.quit()
    f.close()


# send mail to admin list
def send_mail(c, body):
    if not c[9]:
        return

    src = c[2] + " <nobody@example.com>"
    dest = "admins@stusta.mhn.de"

    body.seek(0)
    msg = MIMEText(body.read())
    msg['Subject'] = c[0]
    msg['From'] = src
    msg['To'] = dest
    s = smtplib.SMTP('mail.stusta.mhn.de')
    s.sendmail(src, [dest], msg.as_string())
    s.quit()


def main(argv=sys.argv):
    # collect pages
    site = mwclient.Site('wiki.stusta.mhn.de', path='/')
    category = site.Pages['Category:News']

    for page in category:
        c = scrape(site, page)
        # dispatch news to ng if posted during previous full hour
        interval = 60*60
        newstime = int(time.mktime(c[1]))
        curtime = int(time.time() - interval)
        if curtime / interval == newstime / interval:
            body = write_body(c)
            send_mail(c, body)

            # create ng header and append text
            posting = write_ng(c)
            body.seek(0)
            shutil.copyfileobj(body, posting)
            send_ng(posting)

            #posting.seek(0)
            #print("\n\nPOSTING")
            #for line in posting:
            #    sys.stdout.write(line)


if __name__ == '__main__':
    sys.exit(main())
