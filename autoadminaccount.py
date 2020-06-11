#!/usr/bin/env python3
import csv
from email.message import EmailMessage
from email.utils import localtime
import secrets
import smtplib
import string
import sys


import mwclient

ADMINGROUP = 'sysop'


def send_mail(admin, username, pw):
    body = f'''
Hallo {admin['vorname']},

der StuStaNet e.V. freut sich, dich als neuen Admin begrüßen zu dürfen!

Eine der besten Quellen für unsere Projekte ist das StuSta Wiki.
Vielleicht kennst du es auch schon.
Wir einen neuen Account für dich erstellt, mit dem du berechtigt
bist, die Adminseiten im Wiki abzurufen.

Hier sind die Zugangsdaten:

    Username: {username}
    Password: {pw}

Du kannst dich damit auf https://wiki.stusta.de einloggen.
Das Passwort kannst du dann unter 'Einstellungen > Passwort ändern' neu setzen.
Links sollte eine neue Liste unter dem Namen 'Admin-Bereich' erschienen sein.

Lesenswerte Artikel sind zum Beispiel:
    - https://wiki.stusta.de/Admin_werden, wo du allgemeine Informationen zur
      Admintätigkeit findest
    - https://wiki.stusta.de/Admin:ToDo, wo wir aktuell laufende/geplante
      Projekte dokumentieren
    - https://wiki.stusta.de/Infoseite, wo unsere kommenden Events dokumentiert
      sind. Schau doch mal vorbei!

Bis Bald,
dein StuStaNet e.V.

PS: Falls du bereits einen Wiki Account besitzt und diesem Adminrechte geben
willst, antworte uns mit deinem alten Usernamen auf diese Mail.
'''[1:-1]
    msg = EmailMessage()
    msg.set_content(body)
    msg['subject'] = 'Deine StuSta Wiki Zugangsdaten'
    msg['date'] = localtime()
    msg['from'] = 'StuStaNet e.V. Vorstand' + " <vorstand@mail.stusta.de>"
    msg['to'] = admin['mail']
    msg['reply-to'] = 'StuStaNet e.V. Vorstand' + " <vorstand@mail.stusta.de>"
    s = smtplib.SMTP('mail.stusta.de')
    s.send_message(msg)
    s.quit()



def username_from_name(vorname, nachname):
    vl = vorname.lower()
    nl = nachname.lower()
    v = chr(ord(vl[0])-ord('a')+ord('A')) + vl[1:]
    n = chr(ord(nl[0])-ord('a')+ord('A')) + nl[1:]
    return v + n


def get_creds(fname):
    with open(fname, 'r') as f:
        lines = f.read().split('\n')

    user = lines[0]
    pw = lines[1]
    return user,pw


def gen_pw(length):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))


# https://www.mediawiki.org/wiki/API:Account_creation
def create_account(site, user, password, email=None):
    a = site.raw_api(action="query", meta="tokens", type="createaccount")
    token = a.get('query').get('tokens').get('createaccounttoken')
    if email is None:
        return site.raw_api(action="createaccount",
                            createreturnurl="http://example.com",
                            createtoken=token,
                            username=user,
                            password=password,
                            retype=password).get('createaccount').get('status') == 'PASS'
    else:
        return site.raw_api(action="createaccount",
                            createreturnurl="http://example.com",
                            createtoken=token,
                            username=user,
                            password=password,
                            retype=password,
                            email=email).get('createaccount').get('status') == 'PASS'


def user_exists(site, username):
    m = list(site.users([username]))
    return 'missing' not in m[0]


def is_in_admin(site, username):
    if not user_exists(site, username):
        return False
    return ADMINGROUP in list(site.users([username]))[0].get('groups')



def add_to_group(site, username, group):
    a = site.raw_api(action="query", meta="tokens", type="userrights")
    token = a.get('query').get('tokens').get('userrightstoken')
    return site.raw_api(action="userrights", user=username,
                     add=group, token=token).get('userrights').get('added').__len__() != 0


def add_to_admin(site, username):
    return add_to_group(site, username, ADMINGROUP)



def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} alladmins.csv\ne.g.: cat haus*.csv | {sys.argv[0]}")
    # load admin csv from stdin
    if sys.argv[1] == "-":
        r = csv.DictReader(sys.stdin, delimiter=',', quotechar='"', lineterminator='\n', fieldnames=('vorname','nachname','zimmer','mail','type','memberid'))
        admins = list(r) # list of dicts
    else:
        r = csv.DictReader(open(sys.argv[1],'r'), delimiter=',', quotechar='"', lineterminator='\n', fieldnames=('vorname','nachname','zimmer','mail','type','memberid'))
        admins = list(r) # list of dicts


    # connect and login to wiki
    site = mwclient.Site('wiki.stusta.de', path='/')
    user, pw = get_creds('creds.txt')
    site.login(user, pw)


    for admin in admins:
        print(f"Checking admin {admin}")
        user_created = False
        user_added_to_admin = False
        username = username_from_name(admin['vorname'], admin['nachname'])
        pw = "Du hast bereits Zugang zu deinem Account"
        if not user_exists(site, username):
            pw = gen_pw(16)
            if not create_account(site, username, pw):
                print(f"Failed to create account for {admin}")
                continue
            user_created = True
        if not is_in_admin(site, username):
            if not add_to_admin(site, username):
                print(f"Failed to add {admin} to admin group")
                continue
            user_added_to_admin = True

        print(f"Created User: {user_created}, Added To Admin Group: {user_added_to_admin}")
        if user_created or user_added_to_admin:
           send_mail(admin, username, pw)

if __name__ == "__main__":
    main()
