#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2016 Julien Schmidt <js@stusta.net>

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys, os, re
import configparser
import subprocess
import datetime
import argparse
import requests
import time

config = configparser.RawConfigParser()
config.read(os.path.dirname(os.path.realpath(__file__)) + '/upgrade.ini')
cfg = config.get

wiki_dir = cfg('wiki', 'dir')
db_dump_dir = cfg('backup', 'db_dump_dir')
bup_dir = cfg('backup', 'bup_dir')
bup_idx = cfg('backup', 'bup_idx')
composer_home = cfg('env', 'composer_home')
php_service = cfg('env', 'php_service')
proxy = cfg('env', 'proxy')
extensions_dir = wiki_dir+'extensions/'
extensions_git = cfg('wiki', 'extensions_git').split(',')
extensions = [sub for sub in os.listdir(extensions_dir) if os.path.isdir(os.path.join(extensions_dir, sub))]
skins_dir = wiki_dir+'skins/'
skins_git = cfg('wiki', 'skins_git').split(',')
skins = [sub for sub in os.listdir(skins_dir) if os.path.isdir(os.path.join(skins_dir, sub))]

# Simple output for non-terminal?
out_simple = False

def log(msg):
    print(msg)

def step(msg):
    if out_simple:
        print('\n:: '+msg+' ::')
        return
    print('\n\x1b[40m\x1b[95m'+msg+' ...\x1b[0m')

def info(k, v=''):
    if out_simple:
        if v == '':
            print('[INFO] '+k)
        else:
            print('[INFO] '+k+': '+v)
        return
    if v == '':
        print('\x1b[94m' + k + '\x1b[0m')
        return
    print('\x1b[94m' + k + '\x1b[0m: ' + v)

def warn(msg):
    if out_simple:
        print('[WARN] '+msg)
    else:
        print('\x1b[40m\x1b[93mWARN\x1b[0m: '+msg)

def fail(msg=''):
    if out_simple:
        if msg != '':
            print('[FAIL] '+msg)
    else:
        print('\x1b[40m\x1b[91mFAILED!\x1b[0m: '+msg)
    exit(-1)

def success(msg, code):
    if out_simple:
        print('[SUCCESS] '+msg)
    else:
        print('\x1b[40m\x1b[92mSUCCESS\x1b[0m: '+msg)
    exit(code)

def get_cmd(cmd, cwd=wiki_dir):
    sys.stdout.flush()
    out = subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    return (out[0].decode('utf-8').strip(), out[1].decode('utf-8').strip())

def run_cmd(cmd, cwd=wiki_dir):
    sys.stdout.flush()
    return subprocess.Popen(cmd, cwd=cwd, shell=True).wait()

def get_branches(data):
    return re.findall('origin/(REL[0-9]_[0-9][0-9]?)\\n', data, re.S)

def branch_version(s):
    if len(s) == 7:
        return int(s[3])*100 + int(s[5])*10 + int(s[6])
    if len(s) == 6:
        return int(s[3])*100 + int(s[5])
    return -1

def version_is_stable(version):
    if version.startswith('REL'):
        version = version[3:].replace('_', '.') + ".0"
    # check if 1.xx.0 was tagged (initial stable release)
    return get_cmd('git tag -l ' + version)[0] == version

def get_current_version():
    return get_cmd('git fetch && git rev-parse --abbrev-ref HEAD')[0]

def get_newest_version(stable=True):
    process = subprocess.Popen('git branch -r', cwd=wiki_dir, shell=True, stdout=subprocess.PIPE).stdout.read()
    branches = sorted(get_branches(process.decode("utf-8")), key=lambda v: branch_version(v))
    if len(branches) < 1:
        return None
    i = len(branches)-1
    branch = branches[i]
    if stable:
        while not version_is_stable(branch):
            info(branch + " is not stable yet.")
            if i is 0:
                return None
            i -= 1
            branch = branches[i]
    return branch

def backup_db():
    now = datetime.datetime.now()
    backup_name = now.strftime("wiki_%Y-%m-%d_%H-%M")
    db_name = cfg('backup', 'db_name')
    db_user = cfg('backup', 'db_user')
    db_pass = cfg('backup', 'db_pass')
    file = db_dump_dir + backup_name + '.sql.gz'
    return run_cmd('mysqldump -u '+db_user+' --password='+db_pass+' '+db_name+' | gzip > '+file)

def backup_files():
    cmd = 'BUP_DIR='+bup_dir+' bup save -n '+bup_idx+' -c -q '+wiki_dir+''
    info(cmd)
    return run_cmd(cmd)

def check_git_module_update(subdir):
    git_dir = wiki_dir+subdir+'/'
    ret = run_cmd('git remote update', cwd=git_dir)
    if ret:
        warn('git pull failed for '+subdir+'. Skipping...')
        return False
    local = get_cmd('git rev-parse @', cwd=git_dir)[0]
    remote = get_cmd('git rev-parse @{u}', cwd=git_dir)[0]
    return local != remote

def update_git_module(subdir, version=None):
    git_dir = wiki_dir+subdir+'/'
    
    if version:
        upgrade_cmd = 'git pull && git checkout '+version
        ret = run_cmd(upgrade_cmd, cwd=git_dir)
    else:
        ret = run_cmd('git pull', cwd=git_dir)
    
    if ret:
        warn('git pull failed for '+subdir)
        return ret
    ret = run_cmd('git submodule update --init --recursive', cwd=git_dir)
    if ret:
        warn('failed to update submodules')
        return ret

def update_extensions_git(version=None):
    error = 0
    for ext in extensions_git:
        info('Updating '+ext)
        ret = update_git_module('extensions/'+ext, version)
        if ret:
            error = 1
    return error

def update_skins_git(version=None):
    error = 0
    for skin in skins_git:
        info('Updating '+skin)
        ret = update_git_module('skins/'+skin, version)
        if ret:
            error = 1
    return error

def check_minor_upgrade():
    need_update = False

    step('Checking for mediawiki update')
    ret = run_cmd('git remote update')
    if ret:
        fail('could not update get remote')
    local = get_cmd('git rev-parse @')[0]
    info('local', local)
    remote = get_cmd('git rev-parse @{u}')[0]
    info('remote', remote)
    base = get_cmd('git merge-base @ @{u}')[0]
    info('base', base)
    if local == remote:
        log('Up-to-date')
    elif local != base:
        fail('Branch was modified. Can not pull!')
    else:
        need_update = True

    step('Checking for Composer updates')
    ret = get_cmd('https_proxy='+proxy+' http_proxy='+proxy+' composer update --no-dev --dry-run --no-progress --no-suggest -n --no-ansi')
    ret = re.findall('([0-9]+) install[s]?, ([0-9]+) update[s]?, ([0-9]+) removal[s]?', ret[1])
    if ret:
        composer_changes = int(ret[0][1])+int(ret[0][2])
        if composer_changes > 1:
            info(str(composer_changes)+' composer changes')
            need_update = True

    step('Checking for extension update')
    for ext in extensions_git:
        has_updates = check_git_module_update('extensions/'+ext)
        if has_updates:
            info('New commits available for extension: '+ext)
            need_update = True
        else:
            info('Up-to-date: '+ext)

    step('Checking for skin update')
    for skin in skins_git:
        has_updates = check_git_module_update('skins/'+skin)
        if has_updates:
            info('New commits available for skin: '+skin)
            need_update = True
        else:
            info('Up-to-date: '+skin)

    if not need_update:
        log('Up-to-date')
    return need_update

def do_minor_upgrade():
    do_upgrade = check_minor_upgrade()
    if not do_upgrade:
        return

    info('Updates available. Proceeding...\n')

    step('Checking wiki dir')
    ret = get_cmd('git status --porcelain --ignore-submodules=all -uno')[0]
    if ret != '':
        fail('Can not update. Wiki dir has changes! (run git status -uno)')

    step('Stop PHP Service')
    ret = run_cmd('sudo /bin/systemctl stop '+php_service)
    if ret:
        fail('Failed to stop PHP Service')

    step('Backing up Database')
    ret = backup_db()
    if ret:
        fail('Database Backup failed')

    step('Backing up Files (without uploads)')
    ret = backup_files()
    if ret:
        fail('Files Backup failed')

    step('Pulling new commits')
    ret = run_cmd('git pull')
    if ret:
        fail('git pull failed')

    step('Updating Submodules')
    ret = run_cmd('git submodule update --init --recursive')
    if ret:
        # asking nicely didn't work...
        ret = run_cmd('git submodule update --init --recursive --force')
    if ret:
        fail('git submodule update failed')

    step('Updating Extensions (Composer)')
    ret = run_cmd('https_proxy='+proxy+' http_proxy='+proxy+' COMPOSER_HOME='+composer_home+' composer update --no-dev -o --apcu-autoloader --no-progress --no-suggest -n --no-ansi')
    if ret:
        fail('composer update failed')

    step('Updating Extensions (git)')
    ret = update_extensions_git()
    if ret:
        fail('updating extensions failed')

    step('Updating Skins (git)')
    ret = update_skins_git()
    if ret:
        fail('updating skins failed')

    step('Run update.php')
    ret = run_cmd('php update.php --quick', cwd=wiki_dir+'maintenance/')
    if ret:
        fail('update.php failed')

    step('Start PHP Service')
    ret = run_cmd('sudo /bin/systemctl start '+php_service)
    if ret:
        fail('Failed to start PHP Service')

    # load Main page to verify status code and fill caches
    step('Making test request')
    time.sleep(3) # give the server a short time to start
    req = requests.get(cfg('wiki', 'check_url'))
    if req.status_code != 200:
        fail('Check URL returned status code '+str(req.status_code))

    success('Done.', 1) # non-zero return code to signal that we made changes

def check_major_upgrade():
    step('Checking for new version')
    newest_version = get_newest_version()
    if newest_version is None:
        fail('no git branches found')
    info('newest version', newest_version)

    current_version = get_current_version()
    info('current version', current_version)

    if branch_version(newest_version) <= branch_version(current_version):
        log('up-to-date')
        return False
    return True

def do_major_upgrade():
    do_upgrade = check_major_upgrade()
    if not do_upgrade:
        return

    info('New version available. Proceeding...\n')

    step('Checking wiki dir')
    ret = get_cmd('git status --porcelain -uno --ignore-submodules=all')[0]
    if ret != '':
        fail('Can not update. Wiki dir has changes! (run git status -uno)')

    step('Stop PHP Service')
    ret = run_cmd('sudo /bin/systemctl stop '+php_service)
    if ret:
        fail('Failed to stop PHP Service')

    step('Backing up Database')
    ret = backup_db()
    if ret:
        fail('Database Backup failed')

    step('Backing up Files (with uploads)')
    ret = backup_files()
    if ret:
        fail('Files Backup failed')

    step('Checkout new mediawiki branch')
    new_version = get_newest_version()
    upgrade_cmd = 'git pull && git checkout '+new_version
    ret = run_cmd(upgrade_cmd)
    if ret:
        fail(upgrade_cmd+' failed!')

    step('Updating Submodules')
    ret = run_cmd('git submodule update --init --recursive')
    if ret:
        # asking nicely didn't work...
        ret = run_cmd('git submodule update --init --recursive --force')
    if ret:
        fail('git submodule update failed')

    step('Updating Extensions (Composer)')
    ret = run_cmd('https_proxy='+proxy+' http_proxy='+proxy+' composer update --no-dev -o --apcu-autoloader --no-progress --no-suggest -n --no-ansi')
    if ret:
        fail('composer update failed')

    step('Updating Extensions (git)')
    ret = update_extensions_git(new_version)
    if ret:
        fail('updating extensions failed')

    step('Updating Skins (git)')
    ret = update_skins_git(new_version)
    if ret:
        fail('updating skins failed')

    step('Run update.php')
    ret = run_cmd('php update.php --quick', cwd=wiki_dir+'maintenance/')
    if ret:
        fail('update.php failed')

    step('Start PHP Service')
    ret = run_cmd('sudo /bin/systemctl start '+php_service)
    if ret:
        fail('Failed to start PHP Service')

    # load Main page to verify status code and warum up HHVM
    step('Making test request')
    time.sleep(3) # give the server a short time to start HHVM
    req = requests.get(cfg('wiki', 'check_url'))
    if req.status_code != 200:
        fail('Check URL returned status code '+str(req.status_code))

    success('Done.', 1) # non-zero return code to signal that we made changes

def main(args):
    global out_simple

    parser = argparse.ArgumentParser()
    parser.add_argument('--simple', help='use simple output for non-terminal', action='store_true')
    parser.add_argument('--major', help='perform a major version upgrade', action='store_true')
    args = parser.parse_args()

    out_simple = args.simple

    if args.major:
        do_major_upgrade()
        return

    ret = 0
    if check_major_upgrade():
        log('new major version available!')
        ret = 2
    do_minor_upgrade()
    exit(ret)

if __name__ == "__main__":
    main(sys.argv)
