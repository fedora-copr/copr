:orphan:

.. _koji_vs_copr:

Koji vs. Copr
=============

The goal of this document is to compare Koji and Copr. Why do we have two
different build systems? What are the goals and differences? And what are the
shared grounds?

Koji is the build system for Linux with looong history. Koji’s goal is to have
a reliable build system where everything is logged and reproducible. You should
be able to repeat the build which happened ten years ago. Or you are able to
produce an update for an environment that is more than 10 years old.

Copr’s goal is to have a low barrier to entry. Contributors can easily create a
workspace (project). They are encouraged to submit many builds. For every pull
request; for every commit; for every distribution and architecture. Copr is
very aggressive in disposing of old builds or failed builds.  Contributors
don’t even have to be sponsored (trusted) “packagers” in FAS.  In Copr, it’s
super easy to provide “optional content” (on top of the default distro
packages).

Common grounds
--------------

Both Koji and Copr use Mock for the build itself. Both systems build the RPMs
from sources stored in a `DistGit <https://github.com/release-engineering/dist-git>`_.

Intentional differences
-----------------------

The signing server in Koji (sigul) is pretty strictly secured. Which makes it
hard to maintain. Copr uses obs-signd from OBS, which is easier to maintain and
allows automatic generation of private GPG keys when a new project is created.
Copr can build only RPMs and modules nowadays while Koji can handle a wide
range of artifacts - base container images, qcows, even windows .exe files. Via
content-generators it also supports modules, java builds, or e.g. Debian
packages.

Deployment differences
----------------------

Copr infrastructure consists of 3 VMs for operating (+1 if you want GPG
signing). All of them can be run in the cloud or even in podmans. The builders
though have to be virtual machines. Can be AWS, OpenStack, on-premise or even a
mixture. But builders cannot be containers (technically possible, but running
builders (Mock) in containers would mean significant limits on what packages
can be built there).  An example of Ansible playbook deployment is available.
Koji on the other hand is quite a big deployment.

Storage itself (as all the old builds are archived) is quite big. With the
database and hub, this is the core of the system. Additional Web UI can be used
but is completely independent of the rest of the system. Some tooling (kojira
which is responsible for regenerating outdated repos, garbage collection, etc.)
is deployed on a fourth machine. Similarly to Copr, all these components can
run anywhere (containers, VMs, etc.). The big difference is the builders
themselves. Due to various low-level (kernel, glibc, ...) and security
requirements (potential environment escapes, interference of other VMs,
containers, host abuse, etc.) builders are not running in an untrusted (read as
“cloud” or “ephemeral”) environment.  Builders are a mixture of VMs on
dedicated HW or the bare-metal hosts themselves. No builders are spawned
on-demand but maintained in an auditable way to improve the security of the
supply chain. Each major Koji deployment handles hundreds of such machines. 


Admin differences
-----------------

For Koji, you need a dedicated admin for day-to-day operation as some
operations can be done only by admin (or privileges users with more
fine-grained permissions) - creating tags, managing repositories, adding new
repositories.  In Copr users can do almost everything. Once set up, you rarely
need the admin to oversee the application.

Things that will never change
-----------------------------

Frontend and API - both applications have different goals and audiences. This
will be unable to merge ever without sacrificing the goals and the audience.

Potential to merge
------------------

Allocating builders - Copr spin off the logic of spinning the builder to
project `resalloc`. The logic in Koji is hardcoded. Right now it is not
possible to share the code. But with some effort, we can share the code.

Worth noting differences
------------------------

Preserving builds
^^^^^^^^^^^^^^^^^
* Koji: Preserves everything (sans scratch builds).
* Copr: Only keeps the last successful build.

Users handling
^^^^^^^^^^^^^^
* Koji: Can have local users.
* Copr: Needs either FAS or Kerberos.

Trusting users
^^^^^^^^^^^^^^
* Koji: Builds are separated into groups via “channel” logic.
  All builds in the same channel share the same builders (except windows builds). When the user escapes the mock’s isolation then he can affect others’ builds. You have some level of trust in your packagers.
* Copr: One builder per unique “sandbox”. VM is only ever re-used by the same user, for the same same project, and… (other conditions), and then recycled. Users can not affect others’ builds.

DistGit
^^^^^^^
* Koji: You need to operate DistGit for Koji. It is writable by users.
* Copr: DistGit is private to Copr itself. Only Copr can write there. On the other hand, it does not require any settings. And DistGit is one of the Copr servers. Copr can build from other DistGit instances, e.g. Koji’s.

Reproducibility
^^^^^^^^^^^^^^^
* Koji: Anything built in Koji needs to be in DistGit first (imported manually). This is not a technical limitation but an administration decision. It can change a bit in the near future (e.g. allowing scratch builds for other SCMs) but for distribution builds it will stay as-is.
* Copr: Can build content hosted anywhere (GitHub, Pagure, or any httpd server hosting a source RPM). The sources can disappear the very next momemnt.

Hosting RPM repositories
^^^^^^^^^^^^^^^^^^^^^^^^
* Koji: Koji doesn’t host repositories, it relies on other systems (Bodhi, Pulp, …) dist-repo (Distribution repositories) capability is built in Koji but it is now used mainly as an input for the compose process and for the public distribution.
* Copr: Copr hosts the built RPMs in DNF/YUM repositories.

Mock configuration
^^^^^^^^^^^^^^^^^^
* Koji: Koji uses an internally maintained Mock configuration, and builds from “locally” maintained repositories that even contain pre-release packages.
* Copr: Copr builds from the official Fedora/EPEL/RHEL/Mageia/… mirrors, using the `mock-core-configs` defaults.

FAQ
---

**If I build something in copr and Koji - will these two builds be approximately the same?**

In most cases, the answer is yes. But there are reasons where things can go wild. The basic ones are:
 * Buildroots are not always the same due to the current development phase in Koji vs copr using only released packages.
 * Builders make a difference. Not for the most packages but anything relying on HW - e.g. querying instruction sets and instructing the compiler to use them will affect the build. Similar issues can be seen with dependencies on particular kernel features.

