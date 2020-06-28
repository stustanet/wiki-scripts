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

import re
import smtplib
import sys
import urllib.parse
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import localtime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

import mwclient
import pytz
from bs4 import BeautifulSoup
from ics import Event, Calendar


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
            for line in lines:
                if line.startswith("|von="):
                    start = line[5:]
                elif line.startswith("|bis="):
                    end = line[5:]
                elif line.startswith("|Ort="):
                    location = line[5:]
            if start != "":
                body += "Datum: " + start
                if end != "":
                    body += " bis " + end
                body += "\n"
            if location != "":
                body += "Ort: " + location + "\n"

        else:
            text += item + "\n"

    calendar = None
    try:
        tz = pytz.timezone('Europe/Berlin')
        starttime = tz.localize(datetime.strptime(start, "%Y/%m/%d %H:%M:%S"))
        event = Event()
        event.name = entry['Titel']
        event.begin = starttime
        try:
            endtime = tz.localize(datetime.strptime(end, "%Y/%m/%d %H:%M:%S"))
        except ValueError:
            # default to 2 hours duration
            endtime = starttime + timedelta(hours=2)
        event.end = endtime
        if location != "":
            event.location = location
        text = page.text()
        ms = [re.search(r"\|Zusammenfassung=(.*)", line)
              for line in text.split('\n')]
        ms = [m for m in ms if m is not None]
        if len(ms) > 0:
            event.description = ms[0].groups()[0]

        calendar = Calendar()
        calendar.events.add(event)
    except ValueError:
        print(f"Value error: couldn't parse date {start}")
        calendar = None

    body += "Zusammenfassung:\n"
    body += entry['Zusammenfassung']
    body += "\n\n\n"

    text = ''.join(BeautifulSoup(
        text, "html.parser").findAll(text=True)).strip()
    body += text

    body += "\n\n\n"
    body += "Quelle: https://wiki.stusta.de/" + \
        urllib.parse.quote(entry['Page'].replace(" ", "_"))
    body += "\n\n-- \nMehr Informationen: https://info.stusta.de\n"
    return (body, calendar)


def attach_calendar(msg, calendar):
    ical_atch = MIMEText('text', 'calendar', 'utf-8')
    ical_atch.set_payload(str(calendar).encode("utf-8"), 'utf-8')
    ical_atch.add_header('Content-Disposition',
                         'attachment; filename="invite.ics"')
    msg.attach(ical_atch)


# send mail to announce list
def send_mail(subject, author, body, calendar=None):
    from_addr = "no-reply@mail.stusta.de"
    to_addr = "announce@stusta.de"
    if calendar:
        msg = MIMEMultipart()
        msg['date'] = str(localtime())
    else:
        msg = EmailMessage()
        msg['date'] = localtime()
    msg['subject'] = subject
    msg['from'] = author + f" <{from_addr}>"
    msg['to'] = to_addr
    msg['reply-to'] = "StuStaNet e. V. Admins <admins@lists.stusta.de>"

    if calendar:
        msg.attach(MIMEText(body, 'plain'))
        attach_calendar(msg, calendar)
    else:
        msg.set_content(body)

    smtp = smtplib.SMTP('mail.stusta.de')
    smtp.sendmail(from_addr, to_addr, msg.as_string())
    smtp.quit()


def main():
    site = mwclient.Site('wiki.stusta.de', path='/')

    results = site.get('cargoquery',
                       tables='News',
                       fields='_pageName=Page,Titel,Autor,Zusammenfassung,Datum',
                       where='Infoseite=1 AND Kategorie="StuStaNet" AND TIMESTAMPDIFF(HOUR,Datum,NOW())<1',
                       order_by='Datum ASC',
                       format='json',
                       )

    for res in results['cargoquery']:
        entry = res['title']
        author = entry['Autor']
        if author == "":
            author = "Infoseite"
        subject = entry['Titel']
        send_mail(subject, author, *format_news(
            entry, site.pages[entry['Page']]))


if __name__ == '__main__':
    sys.exit(main())
