import dnf
import sys

from urlgrabber import grabber

yes = set(['yes','y', ''])
no = set(['no','n'])

class Copr(dnf.Plugin):
    """DNF plugin supplying the 'copr' command."""

    #name = 'copr'

    def __init__(self, base, cli):
        """Initialize the plugin instance."""
        super(Copr, self).__init__(base, cli)
        if cli is not None:
            cli.register_command(CoprCommand)

class CoprCommand(dnf.cli.Command):
    """ Copr plugin for DNF """
    aliases = "copr"

    def run(self.args):
        # FIXME this should do dnf itself (BZ#1062889)
        if os.geteuid() != 0:
            raise dnf.exceptions.Error('This command has to be run under the root user.')
        try:
            subcommand, project_name, chroot = extcmds
        except ValueError:
            raise ValueError('exactly three additional parameters to copr command are required')
        repo_filename = "/etc/yum.repos.d/{}.repo".format(project_name.replace("/", "_"))

        if subcommand == "enable":
            #http://copr.fedoraproject.org/coprs/larsks/rcm/repo/epel-7-x86_64/
            base_url = "http://copr.fedoraproject.org"
            api_path = "/coprs/{0}/repo/{1}/".format(project_name, chroot)

            self._ask_user()
            ug = grabber.URLGrabber()
            # FIXME when we are full on python2 urllib.parse
            try:
                fn = ug.urlgrab(base_url+api_path, filename=repo_filename)
            except grabber.URLGrabError, e:
                raise dnf.exceptions.Error(str(e)), None, sys.exc_info()[2]
            self.base.read_all_repos()
        else:
            raise dnf.exceptions.Error(_('Unknown subcommand {}.').format(subcommand))
 
    def _ask_user(self):
        question = """
You are going to enable Copr repository. Please not that this repository is not
part of Fedora and may have various quality and Fedora distribution have no
power over this repository and can not enforce some quality or security level.
 Please do not file bug reports about this packages in Fedora bugzilla.
In case of problems you should contact owner of this repository.
Do you want to continue? [Y/n]: """
       answer = raw_input(question).lower()
       while not ((answer in yes) or (answer in no)):
           answer = raw_input(question).lower()
       if answer in yes:
           return
       else:
           raise dnf.exceptions.Error('Safe and good answer. Exiting.')
