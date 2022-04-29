#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2016 Julien Schmidt <js@stusta.net>
            2021, 2022 Tobias Juelg <jobi@stusta.net>

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

import sys
import os
import re
import configparser
import subprocess
import argparse
import time

import requests


class MediaWikiUpdater:
    """MediaWikiUpdater is a utility for automatic updates of MediaWiki"""

    def __init__(self, out_simple=False):
        config = configparser.RawConfigParser()
        config.read(os.path.dirname(
            os.path.realpath(__file__)) + '/upgrade.ini')
        cfg = config.get

        self.wiki_dir = cfg('wiki', 'dir')

        self.db_name = cfg('backup', 'db_name')
        self.db_user = cfg('backup', 'db_user')
        self.db_pass = cfg('backup', 'db_pass')

        self.db_dump_dir = cfg('backup', 'db_dump_dir')

        self.borg_dir = cfg('backup', 'borg_dir')
        self.borg_base = cfg('backup', 'borg_base')

        self.composer_home = cfg('env', 'composer_home')
        self.php_service = cfg('env', 'php_service')
        self.proxy = cfg('env', 'proxy')

        self.extensions_dir = self.wiki_dir + 'extensions/'
        self.extensions_git = cfg('wiki', 'extensions_git').split(',')
        self.extensions = [sub for sub in os.listdir(
            self.extensions_dir) if os.path.isdir(os.path.join(self.extensions_dir, sub))]

        self.skins_dir = self.wiki_dir + 'skins/'
        self.skins_git = cfg('wiki', 'skins_git').split(',')
        self.skins = [sub for sub in os.listdir(
            self.skins_dir) if os.path.isdir(os.path.join(self.skins_dir, sub))]

        self.check_url = cfg('wiki', 'check_url')

        # Simple output for non-terminal?
        self.out_simple = out_simple

    @staticmethod
    def log(msg):
        print(msg)

    def step(self, msg):
        if self.out_simple:
            print('\n:: ' + msg + ' ::')
            return
        print('\n\x1b[40m\x1b[95m' + msg + ' ...\x1b[0m')

    def info(self, key, value=''):
        if self.out_simple:
            if key == '':
                print('[INFO] ' + key)
            else:
                print('[INFO] ' + key + ': ' + value)
            return
        if value == '':
            print('\x1b[94m' + key + '\x1b[0m')
            return
        print('\x1b[94m' + key + '\x1b[0m: ' + value)

    def warn(self, msg):
        if self.out_simple:
            print('[WARN] ' + msg)
        else:
            print('\x1b[40m\x1b[93mWARN\x1b[0m: ' + msg)

    def fail(self, msg=''):
        if self.out_simple:
            if msg != '':
                print('[FAIL] ' + msg)
        else:
            print('\x1b[40m\x1b[91mFAILED!\x1b[0m: ' + msg)
        sys.exit(-1)

    def success(self, msg, code):
        if self.out_simple:
            print('[SUCCESS] ' + msg)
        else:
            print('\x1b[40m\x1b[92mSUCCESS\x1b[0m: ' + msg)
        sys.exit(code)

    def get_cmd(self, cmd, cwd=None):
        if not cwd:
            cwd = self.wiki_dir
        sys.stdout.flush()
        out = subprocess.Popen(cmd, cwd=cwd, shell=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        return (out[0].decode('utf-8').strip(), out[1].decode('utf-8').strip())

    def run_cmd(self, cmd, cwd=None):
        if not cwd:
            cwd = self.wiki_dir
        sys.stdout.flush()
        return subprocess.Popen(cmd, cwd=cwd, shell=True).wait()

    @staticmethod
    def get_branches_str(data):
        return re.findall('origin/(REL[0-9]_[0-9][0-9]?)\\n', data, re.S)

    @staticmethod
    def __branch_version(version_str):
        if len(version_str) == 7:
            return int(version_str[3]) * 100 + int(version_str[5]) * 10 + int(version_str[6])
        if len(version_str) == 6:
            return int(version_str[3]) * 100 + int(version_str[5])
        return -1

    def version_is_stable(self, version):
        if version.startswith('REL'):
            version = version[3:].replace('_', '.') + ".0"
        # check if 1.xx.0 was tagged (initial stable release)
        return self.get_cmd('git tag -l ' + version)[0] == version

    def get_current_version(self):
        return self.get_cmd('git fetch && git rev-parse --abbrev-ref HEAD')[0]

    def get_branches(self):
        process = subprocess.Popen(
            'git branch -r', cwd=self.wiki_dir, shell=True, stdout=subprocess.PIPE).stdout.read()
        branches = sorted(self.get_branches_str(process.decode("utf-8")),
                          key=self.__branch_version)
        return branches

    def get_newest_version(self, stable=True):
        branches = self.get_branches()
        if not branches:
            return None
        i = len(branches) - 1
        branch = branches[i]
        if stable:
            while not self.version_is_stable(branch):
                self.info(branch + " is not stable yet.")
                if i == 0:
                    return None
                i -= 1
                branch = branches[i]
        return branch

    def backup_db(self):
        backup_name = "db_dump"
        file = self.db_dump_dir + backup_name + '.tmp'
        ret = self.run_cmd('mysqldump' +
                           ' -u ' + self.db_user +
                           ' --password=' + self.db_pass +
                           ' ' + self.db_name + ' > ' + file)
        if ret == 0:
            os.rename(file, self.db_dump_dir + backup_name + '.sql')
        return ret

    def backup_files_borg(self):
        cmd = f"BORG_REPO={self.borg_dir} "  \
              f"BORG_BASE_DIR={self.borg_base} " + \
              "borg create --compression lz4" + \
              f" ::'{{hostname}}-{{now}}' {self.wiki_dir} " + \
              f" {self.db_dump_dir + 'db_dump.sql'}"
        self.info(cmd)
        return self.run_cmd(cmd)

    def borg_prune(self):
        cmd = f"BORG_REPO={self.borg_dir} " + \
              f"BORG_BASE_DIR={self.borg_base} " + \
              "borg prune --keep-within 2m"
        self.info(cmd)
        return self.run_cmd(cmd)

    def check_git_module_update(self, subdir, version=None):
        git_dir = self.wiki_dir + subdir + '/'

        if version:
            upgrade_cmd = 'git pull && git checkout '+version
            ret = self.run_cmd(upgrade_cmd, cwd=git_dir)
        else:
            ret = self.run_cmd('git pull', cwd=git_dir)

        if ret:
            self.warn('git pull failed for ' + subdir + '. Skipping...')
            return False
        local = self.get_cmd('git rev-parse @', cwd=git_dir)[0]
        remote = self.get_cmd('git rev-parse @{u}', cwd=git_dir)[0]
        return local != remote

    def update_git_module(self, subdir, version):
        git_dir = self.wiki_dir + subdir + '/'

        if version:
            upgrade_cmd = 'git pull && git checkout '+version
        else:
            upgrade_cmd = 'git pull'

        ret = self.run_cmd(upgrade_cmd, cwd=git_dir)
        if ret:
            self.warn('git pull failed for ' + subdir)
            return ret
        ret = self.run_cmd('git submodule update --init --recursive', cwd=git_dir)
        if ret:
            self.warn('failed to update submodules')
        return ret

    def update_extensions_git(self, version=None):
        error = 0
        for ext in self.extensions_git:
            self.info('Updating ' + ext)
            ret = self.update_git_module('extensions/' + ext, version)
            if ret:
                error = 1
        return error

    def update_skins_git(self, version=None):
        error = 0
        for skin in self.skins_git:
            self.info('Updating ' + skin)
            ret = self.update_git_module('skins/' + skin, version)
            if ret:
                error = 1
        return error

    def check_minor_upgrade(self):
        need_update = False

        log = self.log
        info = self.info
        step = self.step
        fail = self.fail
        get_cmd = self.get_cmd
        run_cmd = self.run_cmd

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

        # step('Checking for Composer updates')
        # ret = get_cmd('https_proxy=' + self.proxy + ' http_proxy=' + self.proxy +
        #               ' composer update --no-dev --dry-run --no-progress --no-suggest -n --no-ansi')
        # ret = re.findall(
        #    '([0-9]+) install[s]?, ([0-9]+) update[s]?, ([0-9]+) removal[s]?', ret[1])
        # if ret:
        #     composer_changes = int(ret[0][1]) + int(ret[0][2])
        #     if composer_changes > 1:
        #         info(str(composer_changes) + ' composer changes')
        #         need_update = True

        step('Checking for extension update')
        for ext in self.extensions_git:
            has_updates = self.check_git_module_update('extensions/' + ext)
            if has_updates:
                info('New commits available for extension: ' + ext)
                need_update = True
            else:
                info('Up-to-date: ' + ext)

        step('Checking for skin update')
        for skin in self.skins_git:
            has_updates = self.check_git_module_update('skins/' + skin)
            if has_updates:
                info('New commits available for skin: ' + skin)
                need_update = True
            else:
                info('Up-to-date: ' + skin)

        if not need_update:
            self.log('Up-to-date')
        return need_update

    def do_minor_upgrade(self):
        do_upgrade = self.check_minor_upgrade()
        if not do_upgrade:
            return

        info = self.info
        step = self.step
        fail = self.fail
        success = self.success
        run_cmd = self.run_cmd
        get_cmd = self.get_cmd

        info('Updates available. Proceeding...\n')

        step('Checking wiki dir')
        ret = get_cmd('git status --porcelain --ignore-submodules=all -uno')[0]
        if ret != '':
            fail('Can not update. Wiki dir has changes! (run git status -uno)')

        step('Stop PHP Service')
        ret = run_cmd('sudo /bin/systemctl stop ' + self.php_service)
        if ret:
            fail('Failed to stop PHP Service')

        step('Backing up Database')
        ret = self.backup_db()
        if ret:
            fail('Database Backup failed')

        step('Backing up Files (without uploads)')
        ret = self.backup_files_borg()
        if ret:
            fail('Files Backup failed')

        ret = self.borg_prune()
        if ret:
            fail('Pruning failed')

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

        # step('Updating Extensions (Composer)')
        # ret = run_cmd('https_proxy=' + self.proxy + ' http_proxy=' + self.proxy +
        #               ' COMPOSER_HOME=' + self.composer_home +
        #               ' composer update --no-dev -o --apcu-autoloader --no-progress --no-suggest -n --no-ansi')
        # if ret:
        #     fail('composer update failed')

        step('Updating Extensions (git)')
        ret = self.update_extensions_git()
        if ret:
            fail('updating extensions failed')

        step('Updating Skins (git)')
        ret = self.update_skins_git()
        if ret:
            fail('updating skins failed')

        step('Run update.php')
        ret = run_cmd('php update.php --quick', cwd=self.wiki_dir + 'maintenance/')
        if ret:
            fail('update.php failed')

        step('Start PHP Service')
        ret = run_cmd('sudo /bin/systemctl start ' + self.php_service)
        if ret:
            fail('Failed to start PHP Service')

        # load Main page to verify status code and fill caches
        step('Making test request')
        time.sleep(3)  # give the server a short time to start
        req = requests.get(self.check_url)
        if req.status_code != 200:
            fail('Check URL returned status code ' + str(req.status_code))

        # non-zero return code to signal that we made changes
        success('Done.', 1)

    def check_major_upgrade(self):
        self.step('Checking for new version')
        newest_version = self.get_newest_version()
        if newest_version is None:
            self.fail('no git branches found')
        self.info('newest version', newest_version)

        current_version = self.get_current_version()
        self.info('current version', current_version)

        if self.__branch_version(newest_version) <= self.__branch_version(current_version):
            self.log('up-to-date')
            return False
        return True

    def do_major_upgrade(self, version=None):
        """version needs to be a branch name e.g. REL1_36"""
        if version and version not in self.get_branches():
            fail(f'Version {version} does not exist, please check again if by git branch --list')

        if not version:
        do_upgrade = self.check_major_upgrade()
        if not do_upgrade:
            return

        info = self.info
        step = self.step
        fail = self.fail
        success = self.success
        get_cmd = self.get_cmd
        run_cmd = self.run_cmd

        info('New version available. Proceeding...\n')

        step('Checking wiki dir')
        ret = get_cmd('git status --porcelain -uno --ignore-submodules=all')[0]
        if ret != '':
            fail('Can not update. Wiki dir has changes! (run git status -uno)')

        step('Stop PHP Service')
        ret = run_cmd('sudo /bin/systemctl stop ' + self.php_service)
        if ret:
            fail('Failed to stop PHP Service')

        step('Backing up Database')
        ret = self.backup_db()
        if ret:
            fail('Database Backup failed')

        step('Backing up Files (with uploads)')
        ret = self.backup_files_borg()
        if ret:
            fail('Files Backup failed')

        ret = self.borg_prune()
        if ret:
            fail('Pruning failed')

        step('Checkout new mediawiki branch')
        new_version = version or self.get_newest_version()
        upgrade_cmd = 'git pull && git checkout ' + new_version
        ret = run_cmd(upgrade_cmd)
        if ret:
            fail(upgrade_cmd + ' failed!')

        step('Updating Submodules')
        ret = run_cmd('git submodule update --init --recursive')
        if ret:
            # asking nicely didn't work...
            ret = run_cmd('git submodule update --init --recursive --force')
        if ret:
            fail('git submodule update failed')

        step('Updating Extensions (Composer)')
        ret = run_cmd('https_proxy=' + self.proxy + ' http_proxy=' + self.proxy +
                      ' composer update --no-dev -o --apcu-autoloader --no-progress --no-suggest -n --no-ansi')
        if ret:
            fail('composer update failed')

        step('Updating Extensions (git)')
        ret = self.update_extensions_git(new_version)
        if ret:
            fail('updating extensions failed')

        step('Updating Skins (git)')
        ret = self.update_skins_git(new_version)
        if ret:
            fail('updating skins failed')

        step('Run update.php')
        ret = run_cmd('php update.php --quick', cwd=self.wiki_dir + 'maintenance/')
        if ret:
            fail('update.php failed')

        step('Start PHP Service')
        ret = run_cmd('sudo /bin/systemctl start ' + self.php_service)
        if ret:
            fail('Failed to start PHP Service')

        # load Main page to verify status code and warum up HHVM
        step('Making test request')
        time.sleep(3)  # give the server a short time to start HHVM
        req = requests.get(self.check_url)
        if req.status_code != 200:
            fail('Check URL returned status code ' + str(req.status_code))

        # non-zero return code to signal that we made changes
        success('Done.', 1)


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--simple', help='use simple output for non-terminal', action='store_true')
    parser.add_argument(
        '--major', help='perform a major version upgrade', action='store_true')
    parser.add_argument(
        '-v', '--version', help='update to this version, only supported for major updates', type=str, default=None)
    args = parser.parse_args()

    updater = MediaWikiUpdater(out_simple=args.simple)

    if args.major:
        updater.do_major_upgrade(version=args.version)
        return

    ret = 0
    if updater.check_major_upgrade():
        print('new major version available!')
        ret = 2
    updater.do_minor_upgrade()
    sys.exit(ret)


if __name__ == "__main__":
    main(sys.argv)
