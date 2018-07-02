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