#! /bin/bash

export https_proxy=http://proxy.stusta.de:3128
export HOME=/root

/usr/local/bin/wiki-scripts/upgrade.py --simple > /tmp/wiki_update 2>&1

ret=$?
if [ ret -eq 0 ]; then
    SUBJECT="[UNCHANGED] Wiki Upgrade"
elif [ ret -eq 1 ]; then
    SUBJECT="[SUCCESS] Wiki Upgrade"
else
    SUBJECT="[ERROR] Wiki Upgrade"
fi
cat /tmp/wiki_update | mail root -s "$SUBJECT"
