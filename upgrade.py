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

now = datetime.datetime.now()
backup_name = now.strftime("backup_%Y-%m-%d_%H-%M")
backup_dir = cfg('backup', 'dir')
proxy = cfg('env', 'proxy')
extensions_dir = wiki_dir+'extensions/'
extensions = [sub for sub in os.listdir(extensions_dir) if os.path.isdir(os.path.join(extensions_dir,sub))]
skip_extensions = cfg('wiki', 'skip_extensions').split(',')


# Simple output for non-terminal?
outSimple = False

def log(msg):
	print(msg)

def step(msg):
	if outSimple:
		print('\n:: '+msg+' ::')
		return
	print('\n\x1b[40m\x1b[95m'+msg+' ...\x1b[0m')

def info(k, v=''):
	if outSimple:
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
	if outSimple:
		print('[WARN] '+msg)
	else:
		print('\x1b[40m\x1b[93mWARN\x1b[0m: '+msg)

def fail(msg=''):
	if outSimple:
		if msg != '':
			print('[FAIL] '+msg)
	else:
		print('\x1b[40m\x1b[91mFAILED!\x1b[0m: '+msg)
	exit(-1)

def success(msg,code):
	if outSimple:
		print('[SUCCESS] '+msg)
	else:
		print('\x1b[40m\x1b[92mSUCCESS\x1b[0m: '+msg)
	exit(code)

def get_cmd(cmd, cwd=wiki_dir):
	sys.stdout.flush()
	return subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE).stdout.read().decode("utf-8").strip()

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

def get_current_version():
	return get_cmd('git fetch && git rev-parse --abbrev-ref HEAD')

def get_newest_version():
	p = subprocess.Popen('git branch -r', cwd=wiki_dir, shell=True, stdout=subprocess.PIPE).stdout.read()
	branches = sorted(get_branches(p.decode("utf-8")), key=lambda v: branch_version(v))
	if len(branches) < 1:
		return None
	return branches[len(branches)-1]

def backup_db():
	db_name = cfg('backup', 'db_name')
	db_user = cfg('backup', 'db_user')
	db_pass = cfg('backup', 'db_pass')
	file = backup_dir + backup_name + '.sql.gz'
	return run_cmd('mysqldump -u '+db_user+' --password='+db_pass+' '+db_name+' | gzip > '+file)

def backup_files(skip_uploads=False):
	postfix = ''
	options = ''
	if skip_uploads:
		postfix = '_minor'
		options = ' --exclude-tag-all=no_minor_backup.tag'
	file = backup_dir + backup_name + postfix + '.tar.gz'
	cmd = 'tar czf '+file+options+' '+wiki_dir+'.'
	return run_cmd(cmd)

def check_minor_upgrade():
	need_update = False

	step('Checking for mediawiki update')
	mediawiki_update = False
	ret = run_cmd('git remote update')
	if ret != 0:
		fail('could not update get remote')
	local = get_cmd('git rev-parse @')
	info('local', local)
	remote = get_cmd('git rev-parse @{u}')
	info('remote', remote)
	base = get_cmd('git merge-base @ @{u}')
	info('base', base)
	if local == remote:
		log('Up-to-date')
	elif local != base:
		fail('Branch was modified. Can not pull!')
	else:
		mediawiki_update = True
		need_update = True

	# Does not werk properly. Doesn't matter, since for major changes the composer.lock has to be edited => new git commit
	#step('Checking for Composer updates')
	#ret = get_cmd('https_proxy='+proxy+' http_proxy='+proxy+' composer update --no-progress --dry-run')
	
	step('Checking for extension update')
	extension_updates = False
	for ext in extensions:
		if ext in skip_extensions:
			continue
		ext_dir = wiki_dir+'extensions/'+ext+'/'
		ret = run_cmd('git remote update', cwd=ext_dir)
		if ret != 0:
			warn('git pull failed for extension: '+ext+'. Skipping...')
			continue
		local = get_cmd('git rev-parse @', cwd=ext_dir)
		remote = get_cmd('git rev-parse @{u}', cwd=ext_dir)
		if local != remote:
			info('New commits available for extension: '+ext)
			extension_updates = True
	
	if extension_updates:
		need_update = True
	
	if not need_update:
		log('up-to-date')
	return need_update

def do_minor_upgrade():	
	do_upgrade = check_minor_upgrade()
	if not do_upgrade:
		return

	info('updates available. proceeding...\n')

	step('Checking wiki dir')
	ret = get_cmd('git status --porcelain -uno')
	if ret != '':
		fail('Can not update. Wiki dir has changes! (run git status -uno)')

	step('Stop HHVM')
	ret = run_cmd('systemctl stop hhvm')
	if ret != 0:
		fail('Failed to stop HHVM')
	
	step('Backing up Database')
	ret = backup_db()
	if ret != 0:
		fail('Database Backup failed')

	step('Backing up Files (without uploads)')
	ret = backup_files(True)
	if ret != 0:
		fail('Files Backup failed')

	step('Pulling new commits')
	ret = run_cmd('git pull')
	if ret != 0:
		fail('git pull failed')
	
	step('Updating Extensions (Composer)')
	ret = run_cmd('https_proxy='+proxy+' http_proxy='+proxy+' composer update')
	if ret != 0:
		fail('composer update failed')

	step('Updating Extensions (git)')
	for ext in extensions:
		if ext in skip_extensions:
			info('Skipping '+ext)
			continue
		info('Updating '+ext)
		ext_dir = wiki_dir+'extensions/'+ext+'/'
		ret = run_cmd('git pull', cwd=ext_dir)
		if ret != 0:
			fail('git pull failed for extension '+ext)
		ret = run_cmd('git submodule update --init --recursive', cwd=ext_dir)
		if ret != 0:
			fail('failed to update submodules')

	step('Run update.php')
	ret = run_cmd('php update.php', cwd=wiki_dir+'maintenance/')
	if ret != 0:
		fail('update.php failed')
	
	step('Start HHVM')
	ret = run_cmd('systemctl start hhvm')
	if ret != 0:
		fail('Failed to start HHVM')

	# load Main page to verify status code and warum up HHVM
	step('Making test request')
	time.sleep(3) # give the server a short time to start HHVM
	r = requests.get(cfg('wiki', 'check_url'))	
	if r.status_code != 200:
		fail('Check URL returned status code '+str(r.status_code))

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

	info('new version available. proceeding...\n')

	step('Checking wiki dir')
	ret = get_cmd('git status --porcelain -uno')
	if ret != '':
		fail('Can not update. Wiki dir has changes! (run git status -uno)')

	step('Stop HHVM')
	ret = run_cmd('systemctl stop hhvm')
	if ret != 0:
		fail('Failed to stop HHVM')

	step('Backing up Database')
	ret = backup_db()
	if ret != 0:
		fail('Database Backup failed')

	step('Backing up Files (with uploads)')
	ret = backup_files()
	if ret != 0:
		fail('Files Backup failed')

	step('Checkout new mediawiki branch')
	new_version = get_newest_version()
	upgrade_cmd = 'git pull && git checkout '+new_version
	ret = run_cmd(upgrade_cmd)
	if ret != 0:
		fail(upgrade_cmd+' failed!')

	step('Updating Extensions (Composer)')
	ret = run_cmd('https_proxy='+proxy+' http_proxy='+proxy+' composer update')
	if ret != 0:
		fail('composer update failed')

	step('Updating Extensions (git)')
	for ext in extensions:
		if ext in skip_extensions:
			info('Skipping '+ext)
			continue
		info('Updating '+ext)
		ext_dir = wiki_dir+'extensions/'+ext+'/'
		ret = run_cmd(upgrade_cmd, cwd=ext_dir)
		if ret != 0:
			fail(upgrade_cmd+' failed for extension '+ext)
		ret = run_cmd('git submodule update --init --recursive', cwd=ext_dir)
		if ret != 0:
			fail('failed to update submodules')

	step('Run update.php')
	ret = run_cmd('php update.php', cwd=wiki_dir+'maintenance/')
	if ret != 0:
		fail('update.php failed')

	step('Start HHVM')
	ret = run_cmd('systemctl start hhvm')
	if ret != 0:
		fail('Failed to start HHVM')

	# load Main page to verify status code and warum up HHVM
	step('Making test request')
	time.sleep(3) # give the server a short time to start HHVM
	r = requests.get(cfg('wiki', 'check_url'))
	if r.status_code != 200:
		fail('Check URL returned status code '+str(r.status_code))

	success('Done.', 1) # non-zero return code to signal that we made changes

def main(args):
	global outSimple

	parser = argparse.ArgumentParser()
	parser.add_argument('--simple', help='use simple output for non-terminal', action='store_true')
	parser.add_argument('--major', help='perform a major version upgrade', action='store_true')
	args = parser.parse_args()

	outSimple = args.simple
	
	if args.major:
		do_major_upgrade()
		return

	do_minor_upgrade()
	if check_major_upgrade():
		log('new major version available!')
		exit(2)

if __name__ == "__main__":
	main(sys.argv)
