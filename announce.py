#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Relays news entries to the announce mailing list.
# To be run with minimal privileges shortly after every full hour.

# Initial version, 10/2010:
#     B. Hof <hof@stusta.net>
# Made a little bit less unbelievably insane, 04/2012:
#     B. Braun <benjamin.braun@stusta.net>,
#     T. Klenze <tobias.klenze@stusta.net>
# Fixed stuff, 06/2016:
#     J. Schmidt <js@stusta.net>
# Fixed AM/PM handling, 02/2017
#     C. Winter <christian.winter@stusta.net>
# Complete rewrite in python3 using the API, 04/2018
#     J. Schmidt <js@stusta.net>

import sys

# retrieving and parsing wiki pages
import mwclient
from bs4 import BeautifulSoup

# formatting
import textwrap
import urllib.parse

# sending the email
import smtplib
from email.message import EmailMessage
from email.utils import localtime

def format_news(entry, page):
    content = page.text()
    content = content.replace("{{!}}", "")
    content = content.split("\n}}\n")

    text = ""
    body = ""
    for item in content:
        if item.startswith("{{StuStaNet-News"):
            continue
        if item.startswith("{{Termin"):
            start = ""
            end = ""
            location = ""
            lines = item.splitlines()
            for l in lines:
                if l.startswith("|von="):
                    start = l[5:]
                elif l.startswith("|bis="):
                    end = l[5:]
                elif l.startswith("|Ort="):
                    location = l[5:]
            if start != "":
                body += "Datum: " + start
                if end != "":
                    body += " bis " + end
                body += "\n"
            if location != "":
                body += "Ort: " + location + "\n"
        else:
            text += item+"\n"

    body += "Zusammenfassung:\n"
    body += entry['Zusammenfassung']
    body += "\n\n\n"

    text = ''.join(BeautifulSoup(text, "html.parser").findAll(text=True)).strip()
    body += text

    body += "\n\n\n"
    body += "Quelle: https://wiki.stusta.de/"+urllib.parse.quote(entry['Page'].replace(" ", "_"))
    body += "\n\n-- \nMehr Informationen: https://info.stusta.de\n"
    return body

    if c['isdate']:
        tmp.write(c['startdate'].encode('utf-8'))
        tmp.write(" bis ")
        tmp.write(c['enddate'].encode('utf-8'))
        tmp.write("\n")
        tmp.write(c['location'].encode('utf-8'))
    tmp.write("\n\n")
    tmp.write(c['text'].encode('utf-8'))
    tmp.write()

    return body


# send mail to announce list
def send_mail(subject, author, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['subject'] = subject
    msg['date'] = localtime()
    msg['from'] = author + " <no-reply@mail.stusta.de>"
    msg['to'] = "announce@lists.stusta.de"
    msg['reply-to'] = "StuStaNet e. V. Admins <admins@lists.stusta.de>"
    s = smtplib.SMTP('mail.stusta.de')
    s.send_message(msg)
    s.quit()

def main(args=sys.argv):
    site = mwclient.Site('wiki.stusta.de', path='/')

    results = site.get('cargoquery',
        tables = 'News',
        fields = '_pageName=Page,Titel,Autor,Zusammenfassung,Datum',
        where = 'Infoseite=1 AND Kategorie="StuStaNet" AND TIMESTAMPDIFF(HOUR,Datum,NOW())<1',
        order_by = 'Datum ASC',
        format = 'json',
    )

    for res in results['cargoquery']:
        entry = res['title']
        author = entry['Autor']
        if author == "":
            author = "Infoseite"
        subject = entry['Titel']
        send_mail(subject, author, format_news(entry, site.pages[entry['Page']]))

if __name__ == '__main__':
    sys.exit(main())
