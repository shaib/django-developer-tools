#!/usr/bin/env python
"""
Obviously this is only useful if you have to deal with Django's
Trac a lot.

Mostly stolen from Jacob Kaplan-Moss, but improved by Jannis Leidel
and Aymeric Augustin.

Reads a config file at ~/.djpatchrc, e.g.:

    [djpatch]
    username = django
    password = guitar

"""
import argparse
import ConfigParser
import os
import re
import subprocess
import sys
import urllib2
import urlparse
import xmlrpclib

# Turn off help, so we print all options in response to -h
conf_parser = argparse.ArgumentParser(add_help=False)
conf_parser.add_argument("-c", "--conf",
                         metavar="FILE", help="Specify config file",
                         default=os.path.expanduser('~/.djpatchrc'))
args, remaining_argv = conf_parser.parse_known_args()
defaults = {
    "patchlevel": -1,           # -1 = autodetect
    "download_only": False,
    "url": "https://code.djangoproject.com/login/xmlrpc",
}
if args.conf:
    if not os.path.exists(args.conf):
        print "Couldn't find config file %s" % args.conf
        raise
    config = ConfigParser.SafeConfigParser()
    config.read([args.conf])
    try:
        items = config.items("djpatch")
        defaults.update(dict(items))
    except ConfigParser.NoSectionError, e:
        print "Error while loading config file %s: %s" % (args.conf, e)

parser = argparse.ArgumentParser(
    # Inherit options from config_parser
    parents=[conf_parser],
    # Don't mess with format of description
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.set_defaults(**defaults)
parser.add_argument("-d",
                    dest="download_only", action="store_true",
                    help="Only download the patch file")
parser.add_argument("-p",
                    dest="patchlevel", type=int, metavar="NUM",
                    help="Strip NUM leading components from file names")
parser.add_argument("-U", "--username",
                    dest="username", type=str, help="Trac username")
parser.add_argument("-P", "--password",
                    dest="password", nargs=1, type=str, help="Trac password")
parser.add_argument("--url",
                    dest="url", type=str, help="Trac XMLRPC URL")
parser.add_argument("ticket",
                    nargs=1, type=int, help="Ticket ID", metavar="TICKET")

args = parser.parse_args(remaining_argv)

if not args.username or not args.password:
    raise SystemExit('No username or password given.')

credentials = ("%s:%s@" % (args.username, args.password))

url = list(urlparse.urlsplit(args.url))
url[1] = credentials + url[1]
url_with_credentials = urlparse.urlunsplit(url)

s = xmlrpclib.Server(url_with_credentials)
name = ''
patch = None

# Look for a patch
attachments = s.ticket.listAttachments(args.ticket[0])
attachments.sort(key=lambda rec: rec[3])
if attachments:
    name = attachments[-1][0]
    patch = s.ticket.getAttachment(args.ticket[0], name).data
    print u"Found a patch"

# Look for a pull request
if not patch:
    pull_req_re = re.compile(r'https://github\.com/django/django/pull/(\d+)')
    for change in reversed(s.ticket.changeLog(args.ticket[0])):
        if change[2] == 'comment':
            match = pull_req_re.search(change[4])
            if match:
                name = match.group(1) + '.diff'
                patch = urllib2.urlopen(match.group(0) + '.diff').read()
                print u"Found a pull request"
                break

# Oops, nothing found
if not patch:
    print u"No patch found, sorry"
    sys.exit(1)

if args.patchlevel == -1:
    if "\n--- a/" in patch and "\n+++ b/" in patch:
        args.patchlevel = 1
    else:
        args.patchlevel = 0

if args.download_only:
    with open(name, 'w') as p:
        p.write(patch)
    print u"Saved '%s'" % name
else:
    cmd = ["git", "apply", "-p%s" % str(args.patchlevel), "-"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=sys.stdout)
    proc.communicate(patch)
