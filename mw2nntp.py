#!/usr/bin/env python
# B. Hof <hof@stusta.net>, 10/2010
# Posts semantic mediawiki news entries via NNTP.  To be run with minimal
# privileges shortly after every full hour

import mwclient
from BeautifulSoup import BeautifulSoup
import time
from tempfile import NamedTemporaryFile
from nntplib import NNTP
import sys
import string

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
	content = content.split("\n}}\n")

	date = False
	startdate = ""
	enddate = ""
	location = ""
	ssn = False
	for item in content:
		if item.find("{{News") != -1 or \
				item.find("{{StuStaNet-News") != -1:
			if item.find("{{StuStaNet-News") != -1:
				ssn = True
			item = item.strip()
			news = item.splitlines()
			postdate = news[1].split('=')[1]
			postdate = time.strptime(postdate, "%Y/%m/%d %H:%M:%S")
			title = news[2].split('=')[1]
			author = news[3].split('=')[1]
			# ignore picture
			if news[4].find("|Zusammenfassung=") == 0:
				summary = string.join(news[4:], " ")
			else:
				summary = string.join(news[5:], " ")
			summary = summary.split('=')[1]
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


# write posting to tmpfile
def write(content):
	tmp = NamedTemporaryFile(mode='w+b')
	try:
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
		tmp.write("Zusammenfassung:\n")
		tmp.write(content[7].encode('utf-8'))
		if content[3]:
			tmp.write("\n")
			tmp.write(content[4].encode('utf-8'))
			tmp.write(" bis ")
			tmp.write(content[5].encode('utf-8'))
			tmp.write("\n")
			tmp.write(content[6].encode('utf-8'))
		tmp.write("\n\n")
		tmp.write(content[8].encode('utf-8'))
		tmp.write("\n\n\n")
		tmp.write("Quelle: http://wiki.stusta.mhn.de/Aktuelles:" \
				+ string.replace(title, " ", "_"))
		tmp.write("\n\n-- \nMehr Informationen: http://info.stusta.mhn.de\n")
	finally:
		return tmp


# dispatch posting to ng server
def send(f):
	s = NNTP('news.stusta.mhn.de')
	#s.set_debuglevel(1)
	f.seek(0)
	try:
		s.post(f)
	except:
		print "Unexpected error:", sys.exc_info()[0]
	s.quit()
	f.close()


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
			posting = write(c)
			posting.seek(0)
			#for line in posting:
			#	sys.stdout.write(line)
			send(posting)


if __name__ == '__main__':
	sys.exit(main())
