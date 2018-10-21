# Wiki Scripts

A collection of scripts enhancing our Mediawiki setup.

## Announce
Relays news entries to the announce mailing list.
To be run with minimal privileges shortly after every full hour.

## Mensa
Updates a wiki page with today's menu in the university canteens.

## MVG Live
Updates a wiki page with the current departure times of the Studentenstadt Metro station.

*Disabled, as it bloats the database*

## SSS (Sprechstundensystemschleuder)
Updates a wiki page with the next office hour dates.

## Upgrade

Helper script to perform the steps required for an upgrade automatically:

* Check if upgrades (minor/major release) for Mediawiki or one of the extensions (supports composer and git) are available
* File backups via [bup](https://github.com/bup/bup)
* Database backups via mysqldump
* Pull updates
* Run `update.php` (Mediawiki maintenance script)
* Perform test request

`upgrade.sh` is a simple wrapper for runs via timers/cronjobs, sending mail reports.

The upgrade script should be run as an unprivileged user but requires the ability to restart the PHP-FPM service. Thus sudo and a whitelisting for the required commands should be confgiured:

```sh
$ visudo

# insert:
www-data ALL=(root) NOPASSWD: /bin/systemctl stop php7.0-fpm.service
www-data ALL=(root) NOPASSWD: /bin/systemctl start php7.0-fpm.service
www-data ALL=(root) NOPASSWD: /bin/systemctl reload php7.0-fpm.service
```