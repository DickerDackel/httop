# httop - "top" for httpd logs (cavemen version)

`httop` follows all given webserver logs, extracts the source IP address, and
counts the hits from that IP over a given time window.

## SYNOPSIS

`httop.py [-h] [--delay DELAY] [--nolines NOLINES] [--window WINDOW] [--logformat {apache,vhosts}] [--logrx LOGRX] file [file ...]`

## OPTIONS

### -d SECONDS, --delay SECONDS

The delay between screen updates.  Default is 1s.

### -n LINES, --nolines LINES

Number of IPs to display.  Default is 10

### -w SECONDS, --window SECONDS

Tracking window.  Hits older than this will be removed from the counter.

### -l NAME, --logformat NAME

Preconfigured log format names.  Currently only these two are supported:

    * apache: IP address is first field in log line
    * vhosts: IP address is second field in log line

Alterernative log formats can be used by providing...

### -r EXPRESSION, --logrx EXPRESSION

Pass a regular expression to extract the source IP from the log.  The first
regular expression group is expected to be the IP address.  E.g. the
expression for the common vhosts log format would be

    `--logrx '^\S+\s(\S+)'

### file ...

One or more log files to track.

## PLATFORM

Windows doesn't support the `select` function, so this is linux/unix only.

## LICENSE

This script is provided under the MIT license.  See LICENSE file for details.
