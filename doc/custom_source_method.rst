:orphan:

.. _custom_source_method:

Custom source method
====================

Build sources (for SRPM) by user-defined script.

The idea behind the script is simple, when the script is run - it's only
mandatory output is specfile, plus optionally any other file needed to
successfully build a source RPM from that spec file (usually tarball(s),
patches, etc.).  By default we expect that the script generates the files in
current working directory (resultdir='.').

Having turing-complete powers and Internet access - the script can do basically
anything to get all the source pieces together.  The only limitation is that it
is executed under non-privileged user (the script is executed in mock chroot,
under 'mockbuild' user).  This brings one major obstacle that you can not
install any RPM packages from within the script; if you *need* to have some
packages pre-installed, you need to specify them "declaratively" as a list of
(srpm)build-dependencies.  The reasons for this design are that (a) it is easier
and and safer to develop scripts which don't require admin access, (b) it is
convenient to write "portable" scripts (even though the script is executed in
rpm-based mock chroot, the script itself can be easily written/tested on e.g.
Gentoo) and (c) it follows the usual workflows of maintainers (install packages
under root, and work the rest of the day as non-root) and mock workflow.


Required configuration for custom method
----------------------------------------

Basically you only have to specify **script** and **chroot** parameter.

- **script** - scipt file content;  written in any scripting language, but pay
  attention to specify shebang properly, e.g. `#! /bin/sh` for (posix) shell
  scripts.  Also note that the interpreter might not be available by default,
  you might have to request its installation via **builddeps** argument).

- **chroot** - (mock) chroot where the script is executed.  By default, the
  `fedora-latest-x86_64` chroot is used, which represents the latest stable
  or `branched <https://fedoraproject.org/wiki/Releases/Branched>`_ Fedora
  version available in Copr at the time of the build request (e.g.
  `fedora-27-x86_64` when `fedora-rawhide-x86_64` represents Fedora 28).


Optional parameters
-------------------

- **builddeps** - space-separated list of packages which are pre-installed into
  the build **chroot** (before the script is executed).

- **resultdir** - where the **script** generates its output. By default, it is
  assumed to be current working directory.


Webhook support
---------------

The only useful webhook for custom source method is the custom web-hook.
Because unlike other methods, custom method implementation doesn't itself pay
attention to webhook payload (json data used e.g. by GitLab to indicate what
type of event triggered the webhok call) nor there's any particular "clone url".

With custom webhook, the payload parsing/analysis is left to the **script** (in
other words it is user's responsibility).  For that purpose custom webhook
handler dumps the webhook payload (if any) into file `$PWD/hook_payload` file
(from the **script** POV).

For example, if GitLab's *merge-request* event from *contributor/project.git* to
*owner/repo.git* "calls" the custom webhook for package *foo*, the **script**
has to parse the `hook_payload` file to detect *the fact* that
*contributor/project.git* should be cloned (instead of *owner/repo.git*) to
generate the sources.

Since this all is in user's hands, it is not technically incorrect to have empty
hook payload, e.g. it is valid to call `curl -X POST <THE_CUSTOM_HOOK_URL>` to
trigger the custom source build method.

Src.RPM
-------

Copr expects that `script` creates SPEC file, tar ball, and patches in the working
directory. We cannot process SRC.RPM. Because some chroots can use technology
which our server cannot recognize. E.g., in the past `rpm` changed compression and
checksum algorithm and rpm from RHEL was unable to process packages from Fedora.

Examples
--------

- Trivial example (only spec file)::

    $ cat script
    #! /bin/sh -x
    curl https://praiskup.fedorapeople.org/quick-package.spec -O

    $ copr add-package-custom PROJECT \
            --name quick-package \
            --script script

    $ copr build-package --name quick-package PROJECT # trigger the build

- Trivial example (use SRC.RPM)::

    $ cat script
    #! /bin/sh -x
    make dist-srpm
    rpmdev-extract redhat/rpm/SRPMS/quick-package-*.src.rpm
    mv quick-package*src/* ./

    $ copr add-package-custom PROJECT \
            --name quick-package \
            --script-builddeps "make rpmdevtools" \
            --script script

    $ copr build-package --name quick-package PROJECT # trigger the build

- Simple example with Python package with git submodules and in-tree sources::

    $ cat script
    #! /bin/sh

    mkdir -p results
    resultdir=$(readlink -f results)

    set -x # verbose output
    set -e # fail the whole script if some command fails

    # obtain the source code
    git clone https://github.com/praiskup/resalloc --recursive --depth 1
    cd resalloc

    # 1. generate source tarball into resultdir
    python setup.py sdist -d "$resultdir"

    # 2. copy the spec file into resultdir, change the release number so each build
    #    has unique name-version-release triplet
    cd rpm
    release='~'$(date +"%Y%m%d_%H%M%S")
    sed "s/\(^Release:[[:space:]]*[[:digit:]]\+\)/\1$release/" resalloc.spec \
        > "$resultdir"/resalloc.spec

    # 3. copy other sources
    cp *.service "$resultdir"

    $ copr add-package-custom PROJECT \
            --name resalloc \
            --script script \
            --script-resultdir results \
            --script-builddeps 'git' \
            --script-chroot fedora-rawhide-x86_64

    $ copr build-package --name resalloc PROJECT # trigger the build

- slightly more complicated examples are documented in `this blog post about
  CI/CD with Copr <https://pavel.raiskup.cz/blog/copr-ci-and-custom-source-method.html>`_.
