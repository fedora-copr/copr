.. _user_documentation:

User Documentation
==================

This section contains information for users of the Copr Build System. You can find a running Copr instance at http://copr.fedorainfracloud.org/.
You may also be interested in the :ref:`developer_documentation` and :ref:`downloads`.

Quick start
-----------

If you are completely new to the COPR build system, follow these steps to get set up quickly:

1) Set up a FAS account here: https://accounts.fedoraproject.org.
2) Log in to COPR (link at the top right corner of the COPR homepage: https://copr.fedorainfracloud.org/).
3) Visit https://copr.fedorainfracloud.org/api/.
4) Copy the generated authentication token into your ``~/.config/copr`` file.
5) Install the copr-cli tool: ``sudo dnf install copr-cli`` (if you are using Fedora).
6) Run ``copr-cli create first-project --chroot fedora-rawhide-x86_64`` to create your first project.
7) Run ``copr-cli build first-project <path to your SRPM>`` to initiate your first build.

If you don't have an SRPM yet, see https://rpm-packaging-guide.github.io/ for instructions on how to build one.

Tutorial
--------

Refer to :ref:`screenshots_tutorial` or :ref:`video_tutorial` for
guidance on interacting with `copr.fedoraproject.org <http://copr.fedoraproject.org/>`_.


How to enable copr repository?
------------------------------

:ref:`how_to_enable_repo`


Public Copr instances
---------------------

Copr is a free software and anyone can maintain their own instance in
case the Fedora Copr instance doesn't suit their needs. This is a list
of known Copr instances:

.. list-table::
   :header-rows: 1

   * - Instance
     - Description
     - Links

   * - https://copr.fedorainfracloud.org
     - |
       | Fedora Copr instance which is also
       | considered to be the default Copr
       | instance by many users and tools.
     - `Contact <https://docs.pagure.org/copr.copr/index.html#communication>`__,
       `Issues <https://github.com/fedora-copr/copr/issues>`__

   * - https://copr.stg.fedoraproject.org
     - |
       | Fedora Copr staging instance is useful for
       | testing the upcoming changes.
       | We periodically delete all its data.
     -

   * - https://eur.openeuler.openatom.cn
     - openEuler Copr instance
     - `Contact <https://mailweb.openeuler.org/hyperkitty/list/infra@openeuler.org/>`__,
       `Issues <https://quickissue.openeuler.org/en/issues/>`__

.. _build_source_types:

Build Source Types
------------------

Copr supports several types of build sources.

URLs
^^^^

This is currently the only method to submit multiple builds at once. First, you need to upload your SRPM
package(s) on a public server and then provide the URL(s) separated by space or a newline. Note that the build
order of the individual launched builds is not guaranteed.

You can also just input a URL to an rpm .spec file (package metadata) that describe the package without
including the actual build sources. The build sources, being again available on a public server under https,
will be then downloaded by COPR automatically during the SRPM build process.

Direct Upload
^^^^^^^^^^^^^

In case, you have your .spec file or srpm stored locally, you can use this method to upload it directly to
COPR from a command-line (by using copr-cli tool) or through COPR web UI.

.. _scm_ref:

SCM
^^^

This method allows you to build RPM(s) from any Git, DistGit, or SVN repository containing a valid .spec file.
The only required argument is **Clone URL** and if the target repository places the .spec file together
with package sources in the root directory and you want to build from master HEAD, it will simply work.
There are more things to configure for more complex cases. E.g. you might want to specify **Subdirectory**
of the target repository if that is where the repository has the package sources placed. See the following
list for the full option description:

- **Type**: SCM type of the repository being pointed to by **Clone URL** (in other words, whether we should use plain `git` or `git svn` for subsequent cloning).
- **Clone URL**: What repository we should clone to obtain the sources.
- **Committish**: What tag, branch, or commit we should check out from the history of the cloned repository. By default HEAD of master branch.
- **Subdirectory**: Where the subsequent SRPM build command (see below) should be executed. The path is relative to the repository root.
- **Spec File**: Path to the spec file relative to the given **Subdirectory**. Note that you can optionally anchor the path with **/** (e.g. **/rpm/example.spec**). If not
  specified the .spec file will be auto-located.

The last optional thing to configure (except for common build configuration option) is the SRPM build method. There are four choices available:
**rpkg**, **tito**, **tito test**, and **make srpm**:

**rpkg**: The default method.  Apart from building packages from any Git or SVN
repository, it also supports building directly from `DistGit`_ repositories.
Note that **rpkg** (as well as **tito** below) is not only a tool to generate
SRPMs but, in fact, it is also a full-fledged package manager
that you can use from your command-line to maintain your (upstream) projects.
You can read more about this tool `here <https://pagure.io/rpkg-util>`__.
Note that starting from December 2021, Copr migrated to the **rpkg-util v3**,
and so :ref:`your spec files need to use the {{{ }}} templates to comply
<rpkg_util_v3>`.

**tito**: is a robust RPM package manager with lots of features and if your project is managed with Tito, this is the tool you want to pick for SRPM generation (which is
one of the many package manager's features). When this option is selected, the latest package GIT tag will be used to build an SRPM. Note that this utility has currently
no support for specifying an alternative .spec file, which means the **Spec Field** is simply ignored when this option is used and .spec file will be always auto-located.
Note that the basic difference between this tool and **rpkg** is that the target repository needs to be initialized with ``tito init`` first before this tool can be used
to build SRPMs from it. You can read more `here <https://github.com/dgoodwin/tito>`__.

**tito test**: With this option selected, again the `tito <https://github.com/dgoodwin/tito>`_ utility will be used to build an SRPM but this time, the **Committish**
value specified above (or HEAD of the master branch if no **Committish** is specified) will be used to build an SRPM. This corresponds to using ``--test`` switch for
``tito`` when it is invoked to generate the SRPM.

.. _`make_srpm`:

**make srpm**: With this method, the user himself/herself will provide the executable script to be used for SRPM generation. If you
would like to use this method, you need to provide ``.copr/Makefile`` (path being relative to the repository root) with ``srpm`` target
in your repository. Into that ``srpm`` target, you can put whatever it takes to generate the SRPM. You can use network and clone another
repository, you can install new packages, and you can do pretty much everything as this is script is run with root privileges inside
a mock chroot. Note that it is run in the mock chroot of the same OS version as the builder host's (usually the latest released Fedora
version). The Makefile's target is invoked like this:

::

    make -f <cloned_repodir>/.copr/Makefile srpm outdir="<outdir>" spec="<spec_path>"

The ``spec`` parameter is what you specify in the **Spec File** field for the SCM source specification and the script
is run in the **Subdirectory** that you can optionally specify in the source section  as well. Note that you can just ignore
the ``spec`` file parameter in the script if there is no use for it. The ``outdir`` parameter specifies where to put the resulting
SRPM so that COPR can find and build it afterwards.

Example of what can be put into ``.copr/Makefile``:

::

    $ cd myrepo
    $ cat .copr/Makefile
    srpm:
        dnf -y install tito
        tito build --builder=SomeBuilder --test --srpm --output=$(outdir)

Note that the other tools (**tito** and **rpkg**) are run in the specified **Subdirectory** as well.

.. _`dist-git method`:

DistGit
^^^^^^^

There's a new option to build from existing DistGit instances in Copr (e.g.,
from Fedora or CentOS DistGit). To build the `foo` package from
CentOS 8, one can do::

    $ copr build-distgit <project> --name foo --distgit centos --commit c8

It's even easier for a Fedora Rawhide package::

    $ copr build-distgit <project> --name foo

because 'fedora' distgit is the default, and we automatically pick the default
branch.

.. note::
    Please note that an SRPM is downloaded from the specified DistGit instance
    only once per Copr build, regardless of the number of chroots you
    build for.

    It **is not** the case that within one Copr build, e.g.
    ``fedora-37-x86_64`` chroot would be built from the ``f37``
    branch, ``fedora-38-x86_64`` from the ``f38`` branch, and
    ``fedora-39-x86_64`` from the ``rawhide`` branch. You can,
    however, use the **Committish** field to specify what DistGit
    branch should be used (by default, it is ``rawhide`` for
    `Fedora DistGit <https://src.fedoraproject.org/>`_).

    The sources from your DistGit branch (e.g. ``rawhide``) can be
    incompatible with some of the target chroots (e.g. ``epel-8-x86_64``)
    because of different dependencies, build tooling, etc. A typical
    workaround is to submit multiple builds, e.g.::

      copr build-distgit ping --name <package> --chroot fedora-rawhide-x86_64 --commit rawhide
      copr build-distgit ping --name <package> --chroot epel-8-x86_64 --commit epel8


PyPI
^^^^

With this source type, you can build python packages directly from `<https://pypi.python.org/pypi>`_. COPR translates those
packages to src.rpm packages automatically by using `pyp2rpm <https://github.com/fedora-python/pyp2rpm>`_ tool.

RubyGems
^^^^^^^^

Similarly to PyPI source type, this allows building gems from `<https://rubygems.org/>`_. The tool for package translation
here is `gem2rpm <https://github.com/fedora-ruby/gem2rpm>`_.


Custom (script)
^^^^^^^^^^^^^^^

This source type uses a user-defined script to generate sources (which are later
used to create SRPM).  For more info, have a look at
:ref:`custom_source_method`.


Working with Packages
---------------------

Specifying the *source build method* (see above) with each package build would
be quite inconvenient.  However, it is possible to define a package in a Copr
project with the *default source* and then trigger the builds using just the
command ``copr build-package OWNER/PROJECT --name PACKAGE_NAME``.  To add or
modify the ``PACKAGE_NAME`` default source, check ``man copr`` for the
``copr add-package-*`` and ``copr edit-package-*`` commands' descriptions.  For
example, the ``copr build-distgit`` build command has the
``copr add-package-distgit`` and ``copr edit-package-distgit`` counterparts.

The ``PACKAGE_NAME`` default source entry is also created with the very first
package build in the project.  Therefore, after the ``copr build-distgit``
action, you can skip the ``add-package-*`` command and go directly to the
``edit-package-*`` command.

See the `Demo: Working with packages <https://www.youtube.com/watch?v=ASSqempxCSI>`_


Reproducing the builds locally
------------------------------

There's a separate document :ref:`reproducing_builds`.


SSH access to Copr builders
---------------------------

Sometimes it is useful to manually debug failed builds not locally but
within the Copr infrastructure. That's why it is possible to allow SSH
access to a copr builder. More information in the `SSH access to Copr
builders <https://frostyx.cz/posts/ssh-access-to-copr-builders>`_ blog
post.


Temporary projects
------------------

If you want have your copr project deleted automatically after some time
(because it is some CI/CD project, some testing stuff, etc.) you can set the
"delete after days" option in web UI or on command-line:
``copr-cli create your-project ... --delete-after-days 10``

Webhooks
--------

Set up an integration with a Git hosting website and get Copr rebuilds for pull requests, tags and commits.

Simple guide:
  1. Create an SCM package and set its default source by specifying an https:// "Clone URL".
  2. Make sure the package auto-rebuild option is checked.
  3. Now you can navigate to **Setting** tab and then **Integrations**
  4. There is your webhook url in the form of ``https://copr.fedorainfracloud.org/webhooks/<GIT_FORGE>/<ID>/<UUID>/``
  5. Finish it by following the Git host specific guide below.

And next time you push anything to your git, Copr will automatically rebuild your package.

Triggerring builds by tag events
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

One forge may have multiple packages. For this reason, Copr needs to know what package or set of
packages should be rebuilt for the tag event. Copr gets this information from the name of the tag, so
it is important that the tag contains the name of the package, in a predefined format, that will
have to rebuild.

The tag name should be in this format: ``PKGNAME-VERSION[-RELEASE]`` with possibility of
replacing the dash with an underscore.

In case you use different tag name patterns (different Copr package name than tag name), Copr
has no idea what package build should be triggered. You have to be explicit and tell Copr your
**copr package name** in the webhook URL like this ``https://copr.fedorainfracloud.org/webhooks/<GIT_FORGE>/<ID>/<UUID>/<copr_package_name>/``.

Consider this example:

Your Copr package name is **my-package** and tag name on Github is only a version e.g. **1.22.3**, in that case
you have to add an optional argument to your URL containing your **copr package name**.

So if your Copr package name is **my-package** your Github URL would be:
``https://copr.fedorainfracloud.org/webhooks/github/<ID>/<UUID>/my_package/``

GitHub
^^^^^^

How to use it:
  1. In your GitHub project, go to **Settings** / **Webhooks**
  2. Click on the **Add webhook** button.
  3. Fill in the Payload URL field with the url above.
  4. Select **application/json** as the content type.
  5. If you want to react to **Tag push events** click **Let me select individual events.** and then select **Branch or tag creation**.
  6. Click the **Add webhook** button.

Gitlab
^^^^^^

How to use it:
  1. In your GitLab project, go to **Settings** / **Webhooks**.
  2. Fill in the URL field with the url above.
  3. Select **Push events** and **Tag push events** (if you want to react to tags) as event triggers.
  4. Click the **Add webhook** button.

Bitbucket
^^^^^^^^^

How to use it:
  1. In your Bitbucket project, go to **Settings** / **Workflow** / **integrations** / **Add webhook**.
  2. Name the hook, e.g., **Copr**.
  3. Fill in the URL field with the url above.
  4. Select to trigger on **Repository Push**.
  5. Click the **Save** button.

Custom webhook
^^^^^^^^^^^^^^

How to use it:
Use the GitLab/GitHub/Bitbucket steps above (when needed), or simply::

    $ curl -X POST https://copr.fedorainfracloud.org/webhooks/custom/<ID>/<UUID>/<PACKAGE_NAME>/

Note that the package of name 'PACKAGE_NAME' must exist within this project, and that the 'POST' http method must be specified.

With custom webhook(s), you can upload data like::

    $ curl -X POST --data "hook payload data" ....

If the ``PACKAGE_NAME`` package configured in your project uses the script-like
"Custom" build method, the POST data will be available as a ``$(CWD)/hook_data``
file while generating RPM sources.  You can handle this fila according to your
needs in the custom script.

There's an advanced possibility to call the custom webhook like::

    $ curl -X POST https://copr.fedorainfracloud.org/webhooks/custom-dir/<OWNER>/<PROJECTNAME>:custom:<SUFFIX>/<UUID>/<PACKAGE_NAME>/
    $ curl -X POST https://copr.fedorainfracloud.org/webhooks/custom-dir/<OWNER>/<PROJECTNAME>:pr:<INT_UID>/<UUID>/<PACKAGE_NAME>/

This way, the build is placed into a custom directory (e.g.
``myproject:custom:pull-request:1`` or ``myproject:pr:123``).  The ``:pr:``
sub-directories have a retention policy;  every such directory is automatically
removed after 40 days of build inactivity.


Pagure Integration
------------------

.. toctree::

   How to automatize Copr builds upon Pagure forge events <user_documentation/pagure_integration>

Custom-location Webhooks
------------------------

You can look here for how to do this: :ref:`webhook_hacking`

Links
-----

* For building package from git:

1) `Tito <https://github.com/dgoodwin/tito>`_ (`blog post <http://miroslav.suchy.cz/blog/archives/2013/12/29/how_to_build_in_copr/index.html>`__ and `another about Tito+Git annex <http://m0dlx.com/blog/Reproducible_builds_on_Copr_with_tito_and_git_annex.html>`_)

2) `dgroc <https://github.com/pypingou/dgroc>`_ (`blog post <http://blog.pingoured.fr/index.php?post/2014/03/20/Introducing-dgroc>`__)

* `Jenkins plugin <https://wiki.jenkins-ci.org/display/JENKINS/Copr+Plugin>`_ (`blog post <http://michal-srb.blogspot.cz/2014/04/jenkins-plugin-for-building-rpms-in-copr.html>`__)

Multilib
--------

In Copr, you cannot build an i386 package into x86_64 repository (also known as
multilib package) like e.g. in Koji.  You can though build for both
multilib-pair chroots (e.g. ``fedora-31-x86_64`` and ``fedora-31-i386``)
separately, and users can enable both multilib-pair repositories - so in turn
all built 32bit and 64bit packages will be available concurrently.

If you want to automatize this, specify that your project is supposed to be
"multilib capable".  Either in commandline::

    copr create --multilib=on [other options]

or by checkbox on ``Project -> Settings`` web-UI page.

When (a) this feature is enabled for project and (b) the project also contains
multilib-pair chroots, the relevant copr web-UI project page will also provide
multilib repo files button (aside the normal one) so user can pick those.  On
top of that, ``dnf copr enable <owner>/<project>`` installs the multilib
repofile automatically instead of the normal one on multilib capable system.

Users can also manually install the multilib repofiles on multilib capable
system regardless of the project settings, those repofile can e.g. look like::

    $ cat /etc/yum.repos.d/rhughes-f20-gnome-3-12.repo
    [copr:copr.fedorainfracloud.org:rhughes:gnome-3-12]
    name=Copr repo for f20-gnome-3-12 owned by rhughes
    baseurl=http://copr-be.cloud.fedoraproject.org/results/rhughes/f20-gnome-3-12/fedora-$releasever-$basearch/
    skip_if_unavailable=True
    gpgcheck=0
    enabled=1

    [copr:copr.fedorainfracloud.org:rhughes:gnome-3-12:ml]
    name=Copr repo for f20-gnome-3-12 owned by rhughes (i386)
    baseurl=http://copr-be.cloud.fedoraproject.org/results/rhughes/f20-gnome-3-12/fedora-$releasever-i386/
    skip_if_unavailable=True
    gpgcheck=0
    cost=1100
    enabled=1

Advanced searching
------------------

There is a large search box on the Copr homepage and a small search
box at the top of every subpage. Both behave in the exact same way, so
use which one you prefer.

Input formats:

- A number - If the searched value is a valid build ID, the page is redirected
  to the build detail page. Otherwise, a fulltext search is performed.
- A string starting with ``@`` (e.g. ``@copr``) - A fulltext search for a group
  name is performed. For example, searching ``@co`` finds all ``@copr``,
  ``@CoreOS``, ``@cockpit``, etc, and all of their projects.
- A string without any formatting - Performs a fulltext search for user
  names, project names, summaries, descriptions, etc.
- A string containing a forward slash (e.g. ``frostyx/foo`` or
  ``@copr/@copr``) - A fulltext is performed for the both owner name and the
  project name. For example, by searching ``@co/co`` a ``@copr/copr-dev`` can be
  found.


Additionally, a part of the search box is a dropdown menu (a button with a caret
symbol) with more searching options:

- A fulltext search limited to the user name
- A fulltext search limited to the group name (this option is equal to searching
  a string that starts with ``@``)
- A fulltext search limited to the project name
- A fulltext search for package names within projects

Status Badges
-------------

Do you want to add such badge: 

.. image:: https://copr.fedorainfracloud.org/coprs/g/mock/mock/package/mock/status_image/last_build.png

to your page? E.g. to GitHub README.md? You can use those urls:

- `https://copr.fedorainfracloud.org/coprs/<username>/<coprname>/package/<package_name>/status_image/last_build.png`
- `https://copr.fedorainfracloud.org/coprs/g/<group_name>/<coprname>/package/<package_name>/status_image/last_build.png`

And this badge will reflect current status of your package.

Mass rebuilds
-------------

Copr can sustain mass-rebuilds and projects with thousands of packages and
builds. A typical use-case for this can be rebuilding all Fedora packages with
some proposal change or rebuilding programming-language modules (PyPI,
RubyGems) as RPMs.

Please follow these recommendations to have the smoothest experience:

- If possible, let us know in advance, so we pay closer attention to the server
  load and making sure everything functions as it should. Please see the
  preferred :ref:`communication channels <communication>`
- Creating AppStream metadata is too slow for large repositories, you might want
  to disable it. Go to your project settings and turn off the
  "Generate AppStream metadata" option, or specify ``--appstream=off``
  when creating or modifying a project in ``copr-cli``.
- When submitting builds, please use ``--background`` parameter to
  make them deprioritized by scheduler (compared to normal
  builds). It's a nice gesture to other users.
- If possible, don't submit all builds at once but rather 1k-5k at the time and
  wait for Copr to process them
- Use :ref:`build_batches` to specify the order of your builds in advance. This
  is useful when some of the packages use other packages in the project as
  dependencies and need to wait until they are built
- Use `pagination
  <https://python-copr.readthedocs.io/en/latest/client_v3/pagination.html>`_
  when accessing the project packages and builds through API

You may consider using an already existing mass-rebuild tool, such as
`mass-prebuild <https://gitlab.com/fedora/packager-tools/mass-prebuild>`_,
`mini-mass-rebuild <https://github.com/hroncok/mini-mass-rebuild>`_,
`copr-autorebuilder <https://pagure.io/copr-autorebuilder>`_, or
`copr-rebuild-tools <https://github.com/fedora-copr/copr-rebuild-tools>`_.


.. _build_batches:

Build batches
-------------

A build batches feature allows you to define the order of your builds
in advance.  This feature is also available in the web-UI, but it is
more convenient from the command-line::

    $ copr build <project> --no-wait <first.src.rpm>
    Created builds: 101010
    $ copr build <project> --no-wait <second.src.rpm> --after-build-id 101010
    Created builds: 101020
    $ copr build <project> --no-wait <third.src.rpm> --with-build-id 101020
    Created builds: 101030

This will create two batches (first with one build 101010 and second
with two builds 101020 and 101030), where second batch isn't started till Copr
finishes the first one.  This way, you can build a tree of dependant build
batches according to your project needs.  See also a related `blog post
<https://pavel.raiskup.cz/blog/build-ordering-by-batches-in-copr.html>`
which goes a little bit more into detail.

Automatic run of Fedora Review tool
-----------------------------------

There's a new per-project config option (e.g. ``copr create --fedora-review``)
that triggers an automatic run of `Fedora Review`_ after each build in such
project, for now only in the ``fedora-*`` chroots.

We don't mark the build failed when the review tool fails for now, and it is up
to the end-user to check the review results in the new ``review.txt`` file
that is created in build results.

Quick HOWTO for the `Package Review`_ time::

    $ copr create review-foo-component --chroot fedora-rawhide-x86_64 --fedora-review
    $ copr build review-foo-component ./foo.src.rpm
    ...
    # wait and see the results!

.. _`Fedora Review`: https://pagure.io/FedoraReview
.. _`Package Review`: https://fedoraproject.org/wiki/Package_Review_Process


RPM Macros
----------

Copr defines custom RPM macros that are available for every build and
can be used inside of a specfile. Please note that these macros are not
available in other build systems, so you should use them as
e.g. ``%?copr_username`` instead of ``%copr_username``.

- ``%copr_username`` - Owner of the project, can be either a user or
  group name, e.g. ``@copr``
- ``%copr_projectname`` - Name of the project, e.g. ``copr-dev``
- ``%vendor`` - This macro identifies the software maintainer of the distributed
  packages, for example:

    - ``Fedora Copr - user frostyx``
    - ``Fedora Copr - group @copr``
    - Users can run ``rpm -qi <package-name> | grep -i vendor`` to identify
      vendor of their installed packages

- ``%buildtag`` - This macro contains an ID of a Copr build,
  e.g. ``.copr5925897``

Macros for SRPM builds:

- ``%dist`` - Copr `undefines %dist for SRPM builds <https://github.com/fedora-copr/copr/commit/2344ea3136f65b9ed04e0bff4b7b26ba06c6fcb1>`_
  to be distro-agnostic
- ``%_disable_source_fetch`` - We set this macro to ``0``. As a
  consequence, it is possible to submit a build from a specfile with a
  fully qualified ``SourceX`` URL and allow the sources to be
  automatically downloaded.

Users are often interested in having parts of their spec file that are evaluated
only in Copr and ignored by Koji. It is easy to do::

  %if 0%{?copr_projectname:1}
  # This happens only in Copr
  %endif

.. _creating_repositories_manually:

Creating repositories manually
------------------------------

After a build is finished, Copr automatically adds its results to the project RPM
repository. When maintaining a large software stack consisting of hundreds of
packages (e.g. KDE or Gnome), it may be useful to disable this feature and
create repositories manually. That way you can atomically move your repository
from one consistent state to another.

In such case, after a build is finished, Copr adds the results only to an
internal ``devel/repodata`` repository. It's results are not available to
users but the repository is enabled for all subsequent builds in the project.
Once you are ready to publish the changes to users, click the
"Regenerate Repositories" button in your project overview.

Please note that there are some historical inconsistencies in the naming of this
feature. There is a "Create repositories manually" checkbox in the project
settings, ``copr-cli create --disable_createrepo`` in CLI, and ``devel_mode`` in
the API. They are all the same feature.


High Performance Builders
-------------------------

About more powerful builders see :ref:`high_performance_builders`.


Subprojects
-----------

This feature is also known as "CoprDirs". Inside a single project,
it is possible to create multiple subprojects, subprepositories, or
subdirectories, depending on your point of view.

Let's show the feature on an example. First, you need to manually create
a project. Then the subprojects are created dynamically when
builds are submitted into them::

  copr create test --chroot fedora-rawhide-x86_64
  PKG=https://github.com/fedora-copr/copr-test-sources/raw/main/hello-2.8-1.src.rpm
  copr build test $PKG
  copr build test:custom:foo $PKG
  copr build test:custom:bar $PKG

This will create a ``test`` project under my namespace and
submit one build directly into the project, one build to the
``test:custom:foo`` subproject, and one into the ``test:custom:bar``
subproject.

The subproject builds are isolated from each other but they can all
see builds from their own repository and from the main ``test`` project
repository.

The subproject name has to start with the project name. It is followed
by either ``:custom:`` or ``:pr:`` and a suffix. The suffix can be
whatever the user wants.

A subproject can be enabled on a user system with::

  dnf copr enable frostyx/test:custom:foo


Modularity
----------

Copr supports multiple `Fedora Modularity <https://docs.fedoraproject.org/en-US/modularity/>`_ features:


- `Building modules <http://frostyx.cz/posts/how-to-build-modules-in-copr>`_
- `Module hotfixes repositories <http://frostyx.cz/posts/module-hotfixes-in-copr>`_ -
  allowing non-module packages to override module packages
- Enabling/disabling modules in the packages buildroot. Let's suppose
  that you need to install a module dependency, e.g.
  ``dnf module install nodejs:16`` to build your package. This can be
  done in Copr by going to a project settings, picking a chroot,
  clicking its "Edit" button, and specifying the "Modules"
  field. Please note, that it can also disable modules.


FAQ
---

.. _`What is the purpose of Copr?`:

.. rubric:: What is the purpose of Copr? :ref:`¶ <What is the purpose of Copr?>`

Copr is a build system available for everybody. You provide the src.rpm and Copr provides a yum repository. Copr can be used for upstream builds, for continuous integration, or to provide a yum repository for users of your project, if your project is not yet included in the standard Fedora repositories. 

You will need a `FAS account <https://accounts.fedoraproject.org>`_ in order to get started.

.. _`What I can build in Copr?`:

.. rubric:: What I can build in Copr? :ref:`¶ <What I can build in Copr?>`

You agree not to use Copr to upload software code or other material
("Material") that:

a. you do not have the right to upload or use, such as Material that
   infringes the rights of any third party under intellectual
   property or other applicable laws;

b. is governed in whole or in part by a license not contained in the
   list of acceptable licenses for Fedora, currently located at
   https://docs.fedoraproject.org/en-US/legal/allowed-licenses,
   as that list may be revised from time to time by the Fedora Council;

c. is categorized as a "Not-Allowed Item" at
   https://docs.fedoraproject.org/en-US/legal/not-allowed-licenses/
   as that page may be revised from time to time by the Fedora
   Council;

d. is designed to interfere with, disable, overburden, damage,
   impair or disrupt Copr or Fedora Project infrastructure;

e. violates any rules or guidelines of the Fedora Project - especially the Fedora Project `Code of Conduct <https://docs.fedoraproject.org/en-US/project/code-of-conduct/index.html>`_ You do **not** need to comply with `Packaging Guidelines <https://docs.fedoraproject.org/en-US/packaging-guidelines/>`_.; or

f. violates any applicable laws and regulations.

It is your responsibility to check licenses and to be sure you can make the resulting yum repo public.

If you think that some repo may be violating a license, you can raise a legal flag - there is a dedicated text area in each project to do so. This will send a notification to the admins and we will act accordingly.

It would be nice if you stated the license of your packages in the Description or Install instructions.

Packages in Copr do **not** need to follow the
`Fedora Packaging Guidelines <https://docs.fedoraproject.org/en-US/packaging-guidelines/>`_,
though they are recommended to do so. In particular, kernel modules
may be built in Copr, as long as they don't violate the license
requirements in point 2. above.

.. _`faq-high-performance-builders`:

.. rubric:: Can you lend me faster Copr builders? :ref:`¶ <faq-high-performance-builders>`

Yes, glad you asking!  But you don't always want this, see — :ref:`high_performance_builders`.

.. _`Is it safe to use Copr?`:

.. rubric::  Is it safe to use Copr? :ref:`¶ <Is it safe to use Copr?>`

This is a two-part question.

1\) Can we trust Copr as a platform?

Copr is free software with its code publicly available for review by
anyone. Internally, it uses the standard Fedora packaging toolset, and
resulting repositories are signed. All Copr servers are deployed
within Fedora infrastructure, and we work closely with the Fedora
Infrastructure team.

2\) Can we trust the software available in Copr?

Only people with FAS accounts are allowed to create projects and build
packages in Copr. That means that you can find out more information
about each project owner and decide for yourself whether you find them
trustworthy or not. You can also see how exactly each build was
submitted, download its SRPM file, and validate the sources and spec
file for yourself.

.. _`How can I enable a Copr repository?`:

.. rubric:: How can I enable a Copr repository? :ref:`¶ <How can I enable a Copr repository?>`

See :ref:`how_to_enable_repo`.

.. _`How can I package software as RPM?`:

.. rubric:: How can I package software as RPM? :ref:`¶ <How can I package software as RPM?>`

There are several tutorials:

- `RPM Packaging Guide <https://rpm-packaging-guide.github.io/>`_
- `Packaging Workshop (video) <http://youtu.be/H4vxkuoimzc>`_ `(and the same workshop from different conference) <https://youtu.be/KdIsoYGSNS8>`_
- `How to create an RPM package <https://fedoraproject.org/wiki/How_to_create_an_RPM_package>`_
- `Creating and Building Packages <http://documentation-devel.engineering.redhat.com/site/documentation/en-US/Red_Hat_Enterprise_Linux/7/html/Packagers_Guide/chap-Red_Hat_Enterprise_Linux-Packagers_Guide-Creating_and_Building_Packages.html>`_
- `How To Make An RPM With Red Hat Package Manager (video) <http://youtu.be/4J_Iksu1fgo>`_
- http://www.rpm.org/max-rpm/
- `Getting Started with RPMs (RH subscribers only) <https://access.redhat.com/videos/214983>`_
- `Advanced packaging workshop (video) <https://youtu.be/vdWnyIbN8uw>`_


.. _`Can I build for different versions of Fedora?`:

.. rubric:: Can I build for different versions of Fedora? :ref:`¶ <Can I build for different versions of Fedora?>`

Yes. Just hit the "Edit" tab in your project and select several chroots, e.g. "fedora-19-x86_64" and "fedora-18-x86_64". After doing so, when you submit the src.rpm, your package will be built for both of those selected versions of Fedora. 

You can build for EPEL as well. 

.. _`Can I have more yum repositories?`:

.. rubric:: Can I have more yum repositories? :ref:`¶ <Can I have more yum repositories?>`

Yes. Each user can have more than one project and each project has one yum repository - to be more precise one repository per chroot.

.. _`Can I submit multiple builds at once?`:

.. rubric:: Can I submit multiple builds at once? :ref:`¶ <Can I submit multiple builds at once?>`

Yes. Just separate them by a space or a new line, but keep in mind that we do not guarantee build order.

.. _`What happens when I try to build a package with the same version number?`:

.. rubric:: What happens when I try to build a package with the same version number? :ref:`¶ <What happens when I try to build a package with the same version number?>`

Nothing special. Your package will just be rebuilt again.

.. _`Can I depend on other packages, which are not in Fedora/EPEL?`:

.. rubric:: Can I depend on other packages, which are not in Fedora/EPEL? :ref:`¶ <Can I depend on other packages, which are not in Fedora/EPEL?>`

Yes, they just need to be available in some yum repository. It can either be another Copr repo or a third-party yum repo (e.g jpackage). Click on "Edit" in your project and add the appropriate repositories into the "Repos" field.
Packages from your project are available to be used at build time as well, but only for the project you are currently building and not from your other projects.

.. _`Can I give access to my repo to my team mate?`:

.. rubric:: Can I give access to my repo to my team mate? :ref:`¶ <Can I give access to my repo to my team mate?>`

Yes. If somebody wants to build into your project and you want give them access, just point them to your Copr project page. They should then click on the "Permission" tab, and request the permissions they want. "Builder" can only submit builds and "Admin" can approve permissions requests. You will then have to navigate to the same "Permission" tab and either approve or reject the request.

.. _`Do you have a command-line client?`:

.. rubric:: Do you have a command-line client? :ref:`¶ <Do you have a command-line client?>`

Yes. Just do ``dnf install copr-cli`` and learn more by ``man copr-cli``.

.. _`Do you have an API?`:

.. rubric:: Do you have an API? :ref:`¶ <Do you have an API?>`

Yes. See the link in the footer of every Copr page or jump directly to the `API page <https://copr.fedorainfracloud.org/api/>`_.

.. _`How long do you keep the builds?`:

.. rubric:: How long do you keep the builds? :ref:`¶ <How long do you keep the builds?>`

We keep one build for each package in one project indefinitely.  All other
builds (old packages, failed builds) are deleted after 14 days.

Note that we keep the build with the greatest EPOCH:NAME-VERSION-RELEASE,
even though that build might not be the newest one.  Also, if there are
two builds of the same package version, it is undefined which one is going
to be kept.

Projects that opted-in for :ref:`creating_repositories_manually`, are
exempt from the old package removal because of technical limitations.

.. _`How is Copr pronounced?`:

.. rubric:: How is Copr pronounced? :ref:`¶ <How is Copr pronounced?>`

In American English Copr is pronounced /ˈkɑ.pɚ/ like the metallic element spelled "copper".

.. _`Why another buildsystem?`:

.. rubric:: Why another buildsystem? :ref:`¶ <Why another buildsystem?>`

We didn't start off to create another buildsystem. We originally just wanted to make building third party rpm repositories easier, but after talking to the koji developers and the developers who are building packages for CentOS we realized that there was a need for a maintainable, pluggable, and lightweight build system.

.. _`Did you consider OBS?`:

.. rubric:: Did you consider OBS? :ref:`¶ <Did you consider OBS?>`

Yes, we did. See `Copr and integration with Koji <http://miroslav.suchy.cz/blog/archives/2013/08/29/copr_and_integration_with_koji/index.html>`_ and `Copr Implemented using OBS <http://miroslav.suchy.cz/blog/archives/2013/08/30/copr_implemented_using_obs/index.html>`_. And the `mailing list discussion <https://lists.fedoraproject.org/pipermail/devel/2013-August/188575.html>`_, as well as the `conclusion <https://lists.fedoraproject.org/pipermail/devel/2013-September/188751.html>`_.

.. _`Can I get notifications from Copr builds?`:

.. rubric:: Can I get notifications from Copr builds? :ref:`¶ <Can I get notifications from Copr builds?>`

Yes, you can. Enable email/irc/android notifications at `Fedora notifications service <https://apps.fedoraproject.org/notifications/>`_.

See blog post `how to consume copr messages from bus <https://pavel.raiskup.cz/blog/copr-messsaging.html>`_.

.. _`What does Copr mean?`:

.. rubric:: What does Copr mean? :ref:`¶ <What does Copr mean?>`

Community projects (formerly Cool Other Package Repositories)

.. _`How can I tell yum to prefer Copr packages?`:

.. rubric:: How can I tell yum to prefer Copr packages? :ref:`¶ <How can I tell yum to prefer Copr packages?>`

Building a package with the same version-release number in Copr as the package distributed in the official Fedora repos is discouraged. You should instead bump the release number. Should you build with the same version-release number, you can tell yum to prefer the Copr packages over the distribution provided packages by adding cost=900 to the .repo file.

.. _`Can Copr build directly from git?`:

.. rubric:: Can Copr build directly from git? :ref:`¶ <Can Copr build directly from git?>`

Yes, it can. See :ref:`scm_ref` source type.

If you want to know more about tools to generate srpm from a Git repo, see:

1) `Tito <https://github.com/dgoodwin/tito>`_ (`blog post <http://miroslav.suchy.cz/blog/archives/2013/12/29/how_to_build_in_copr/index.html>`__)

2) `dgroc <https://github.com/pypingou/dgroc>`_ (`blog post <http://blog.pingoured.fr/index.php?post/2014/03/20/Introducing-dgroc>`__)

.. _`Why doesn't Copr download my updated package?`:

.. rubric:: Why doesn't Copr download my updated package? :ref:`¶ <Why doesn't Copr download my updated package?>`

Sometimes people report that even though they have updated the src.rpm file and submitted the new build, Copr is still using the old src.rpm. This is typically caused when changes are made to the src.rpm file, but the release number was not bumped up accordingly. As a consequence the resulting files have the same URL, so your browser does not bother to fetch new log files and continues to show those files in its cache. Therefore you are still seeing old content from the previous task.

You should press Ctrl+Shift+R to invalidate your cache and reload page

.. _`How can I create new group?`:

.. rubric:: How can I create new group? :ref:`¶ <How can I create new group?>`

Groups membership is handled by `FAS <https://accounts.fedoraproject.org>`_. It can add/remove members to existing group. However it cannot create new group. You can create new group by `creating new fedora-infra ticket <https://pagure.io/fedora-infrastructure/new_issue>`_.
You have to log out and then log in again to Copr so Copr can read your new
settings.  Note also that you might need to wait a few minutes till the
`group list gets synchronized <https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/ipsilon/#_known_issues>`_.
Users also reported that `logging-out first from Ipsilon <https://id.fedoraproject.org/logout>`_ might help with synchronization.

Once copr knows the FAS groups you belong to, you still need to activate the
group.  Go to `my groups <https://copr.fedorainfracloud.org/groups/list/my>`_
page and click on the ``Activate this group`` button.

.. _`I see some strange error about /devel/repodata/ in logs.`:

.. rubric:: I see some strange error about /devel/repodata/ in logs. :ref:`¶ <I see some strange error about /devel/repodata/ in logs.>`

This is intended.
In fact in next release there will be something like "Please ignore the error above".

This is part of feature where you can check in your settings "Create repositories manually". This is intended for big
projects like Gnome or KDE, which consist of hundreds of packages. And you want to release them all at the same time.
But on the other hand it take days to build them. And of course during the buildtime you need to enable that repository,
while at the same time have it disabled/frozen for users.

So if you check "Create repositories manually", we do not run createrepo_c in normal directory, but in ./devel/ directory.
This is directory is always passed to mock with ``skip_if_unavailable=1``.
So if Copr have it, then it is used, otherwise ignored. But if it is missing DNF/YUM print the warning above even if it
is ignored. Currently there is no way to tell DNF/YUM to not print this warning.

.. _`How can I affect the build order, is there a "chain" build support?`:

.. rubric:: How can I affect the build order, is there a "chain" build support? :ref:`¶ <How can I affect the build order, is there a "chain" build support?>`

Build batches can be used to guarantee the order in which the builds are
processed (one build batch can depend on other build batch).
See `blog post <https://pavel.raiskup.cz/blog/build-ordering-by-batches-in-copr.html>`_
with examples for more info.

.. _`Build succeeded, but I don't see the built results!`:

.. rubric:: Build succeeded, but I don't see the built results? :ref:`¶ <Build succeeded, but I don't see the built results!>`

Fedora Copr uses the AWS CDN to spread the HTTP traffic on the built RPM
repositories across the globe, and it implies a lot of caching on the AWS side.

When you (or anyone else in your territory) check the build directory while
the build is still in progress, the web server directory listing gets cached in
CDN - and then the contents of the directory appears unchanged for some time
(even though the build might already be finished and thus the directory updated).

Don't worry, this caching doesn't affect the DNF/YUM behavior - so even though
your browser is misled by caches, package managers always download the latest
contents of the directories.  Either please ignore the inconsistency, or visit
the `non-cached host variant
<http://copr-be.cloud.fedoraproject.org/results/>`_.

.. _`faq-build-timeout`:

.. rubric:: My build failed because of a timeout, why?  :ref:`¶ <faq-build-timeout>`

Builds are not allowed to run forever. The default limit is 5 hours
(18000 seconds) but users can increase it up to 30 hours (108000
seconds).

.. admonition:: Deployment specific

    The `Fedora Copr <https://copr.fedorainfracloud.org/>`_ instance increases
    the maximum limit to 50 hours (180000 seconds).

If the timeout limit is exceeded, the build will be killed
with the following error message::

    !! Copr timeout => sending INT
    Copr build error: Build failed
    Shared connection to builder closed.


.. _`Weird SCM build failure?`:

.. rubric:: Weird SCM build failure? :ref:`¶ <Weird SCM build failure?>`

It worked for me before, but I newly see the ``rpkg`` errors like::

    Running: rpkg srpm --outdir /var/lib/copr-rpmbuild/results ...
    Copr build error: error: Bad source: /var/lib/copr-rpmbuild/results/example-1.0.13.tar.gz: No such file or directory

Please take a look at :ref:`rpkg_util_v3`.

.. _`What is difference between Koji vs. Copr?`:

.. rubric:: What is difference between Koji vs. Copr? :ref:`¶ <What is difference between Koji vs. Copr?>`

See separate page :ref:`koji_vs_copr`.

.. _`faq-autospec`:

.. rubric:: How to deal with Copr and RPMAutoSpec? :ref:`¶ <faq-autospec>`

The easiest way is to use :ref:`DistGit source type <dist-git method>`.  It automatically
expands ``%autorelease`` and ``%autochangelog`` from the cloned dist-git
repository.

If you need to fine tune the process and alter it somehow you can -
Set the source type to "Custom", and use the following script::

    #! /bin/sh -x
    package=<package>
    copr-distgit-client clone "$package" --dist-git fedora
    cd "$package" || exit 1
    .. tweak the spec file or checkout the desired branch ..
    copr-distgit-client sources  # download sources
    copr-distgit-client srpm --outputdir .
    bsdtar xf *.src.rpm -C "$COPR_RESULTDIR"

Set the Buildroot dependencies to ``copr-distgit-client bsdtar``.  Alternatively
you can go even deeper and use ``git rpmdevtools rpmautospec`` deps with::

    git clone <git url> <project name>
    cd <project name>
    spectool -g <spec file>
    rpmautospec process-distgit <spec file> <spec file>

In this case specify the result directory to the same ``<project name>`` string
used in the script.


.. _`I have a problem and I need to talk to a human.`:

.. rubric:: I have a problem and I need to talk to a human.  :ref:`¶ <I have a problem and I need to talk to a human.>`

We do not provide support per se, but try your luck here: :ref:`communication`

.. _`DistGit`: https://clime.github.io/2017/05/20/DistGit-1.0.html
