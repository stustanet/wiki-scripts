#! /bin/bash

export https_proxy=http://proxy.stusta.de:3128
export HOME=/root

/usr/local/bin/wiki-scripts/upgrade.py --simple > /tmp/wiki_update 2>&1

if [ $? -ne 0 ]; then
    SUBJECT="[ERROR] Wiki Upgrade"
else
    SUBJECT="[SUCCESS] Wiki Upgrade"
fi
cat /tmp/wiki_update | mail root -s "$SUBJECT"
