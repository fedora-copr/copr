import dnf
import os
import sys
import platform

from dnf.yum.i18n import _
from urlgrabber import grabber
import urllib
import json

yes = set([_('yes'), _('y')])
no = set([_('no'), _('n'), ''])

class Copr(dnf.Plugin):
    """DNF plugin supplying the 'copr' command."""

    name = 'copr'

    def __init__(self, base, cli):
        """Initialize the plugin instance."""
        super(Copr, self).__init__(base, cli)
        if cli is not None:
            cli.register_command(CoprCommand)
        cli.logger.debug("initialized Copr plugin")

class CoprCommand(dnf.cli.Command):
    """ Copr plugin for DNF """

    aliases = ("copr",)

    @staticmethod
    def get_summary():
        """Return a one line summary of what the command does."""
        return _("""Interact with Copr repositories. Example:
  copr enable rhscl/perl516 epel-6-x86_64
  copr enable ignatenkobrain/ocltoys
  copr disable rhscl/perl516
  copr list ignatenkobrain
""")

    @staticmethod
    def get_usage():
        """Return a usage string for the command, including arguments."""
        return _("""
enable name/project [chroot]
disable name/project
list name""")

    def run(self, extcmds):
        # FIXME this should do dnf itself (BZ#1062889)
        if os.geteuid() != 0:
            raise dnf.exceptions.Error(_('This command has to be run under the root user.'))
        try:
            subcommand = extcmds[0]
            project_name = extcmds[1]
        except ValueError:
            self.cli.logger.critical(
                _('Error: ') + _('exactly two additional parameters to copr command are required'))
            dnf.cli.commands._err_mini_usage(self.cli, self.cli.base.basecmd)
            raise dnf.cli.CliError(_('exactly two additional parameters to copr command are required'))
        try:
            chroot = extcmds[2]
        except IndexError:
            # FIXME Copr should generate non-specific arch repo
            dist = platform.linux_distribution()
            if "Fedora" in dist:
                chroot = ("fedora-%s-x86_64" % dist[2].lower() if "Rawhide" in dist else dist[1])
            else:
                chroot = ("epel-%s-x86_64" % dist[1].split(".", 1)[0], arch)
        repo_filename = "/etc/yum.repos.d/_copr_{}.repo".format(project_name.replace("/", "-"))
        base_url = "http://copr.fedoraproject.org"
        if subcommand == "enable":
            #http://copr.fedoraproject.org/coprs/larsks/rcm/repo/epel-7-x86_64/
            api_path = "/coprs/{0}/repo/{1}/".format(project_name, chroot)

            self._ask_user()
            ug = grabber.URLGrabber()
            # FIXME when we are full on python2 urllib.parse
            try:
                ug.urlgrab(base_url+api_path, filename=repo_filename)
            except grabber.URLGrabError, e:
                raise dnf.exceptions.Error(str(e)), None, sys.exc_info()[2]
            self.cli.logger.info(_("Repository successfully enabled."))
        elif subcommand == "disable":
            # FIXME is it Copr repo ?
            try:
                os.remove(repo_filename)
            except OSError, e:
                raise dnf.exceptions.Error(str(e)), None, sys.exc_info()[2]
            self.cli.logger.info(_("Repository successfully disabled."))
        elif subcommand == "list":
            #http://copr.fedoraproject.org/api/coprs/ignatenkobrain/
            api_path = "/api/coprs/{}/".format(project_name)

            opener = urllib.FancyURLopener({})
            res = opener.open(base_url+api_path)
            try:
                json_parse = json.loads(res.read())
            except ValueError:
                raise dnf.exceptions.Error(_("Can't parse repositories for username '{}'.").format(project_name)), None, sys.exc_info()[2]
            i = 0
            while i < len(json_parse["repos"]):
                print "{0}/{1}".format(project_name, json_parse["repos"][i]["name"])
                i += 1
        else:
            raise dnf.exceptions.Error(_('Unknown subcommand {}.').format(subcommand))

    @classmethod
    def _ask_user(cls):
        question = _("""
You are going to enable Copr repository. Please note that this repository is not
part of Fedora distribution and may have various quality. Fedora distribution
have no power over this repository and can not enforce some quality or security
level.
Please do not file bug reports about this packages in Fedora Bugzilla.
In case of problems you should contact owner of this repository.

Do you want to continue? [y/N]: """)
        answer = raw_input(question).lower()
        answer = _(answer)
        while not ((answer in yes) or (answer in no)):
            answer = raw_input(question).lower()
            answer = _(answer)
        if answer in yes:
            return
        else:
            raise dnf.exceptions.Error(_('Safe and good answer. Exiting.'))
