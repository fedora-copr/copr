:orphan:

.. _high_performance_builders:

Builders in Fedora Copr are too slow!
=====================================

The *normal* Fedora Copr builders are typically fast enough for the vast majority
of package builds.  However, some package builds are extremely
resource-intensive, and our *normal builders* struggle with them.  A notable
example is Blink_-based browsers, which can take even more than 24 hours to
build.

From a build system perspective, this isn't a problem.  You can simply specify
``--timeout 180000`` (in seconds) and be prepared to wait for the build to
finish.  But if you want to expedite your builds, you do have the option to
request *high-performance builders*.

Pros & Cons of *high-performance builders*
------------------------------------------

Once you get them, the *high-performance builders* will handle your builds much
faster.  According to the specification as of October 2023, they are
approximately 8 times faster than the *normal builders*, but the actual speedup
is very task-dependent. They also provide twice as much disk space (280G vs
regular 140G).

The downside is that they are in limited supply. If other users request them at
the same time as you, you'll compete with others, and you may spend a bit longer
waiting in the queue until one such machine is allocated for you (*starting*
phase of the build).

Also, because these machines are costly, we never pre-allocate them (as we do
with the normal builders to generally minimize the initial waiting).  We only
start these *high-performance* ones when a specific build request them.  Waiting
for the corresponding machine to start may take several additional minutes.

It's worth noting that when you configure your project, chroot, or package to
use *high-performance builders*, you will get them, sooner or later.  There's no
magical "fallback to normal builders".  **The rule of thumb** is to avoid using
*high-performance builders* for builds that are expected to complete in less than
two hours on *normal builders*.

How to request *high-performance builders*
------------------------------------------

As of October 2023, we only support *high-performance builders* for ``x86``,
``aarch64`` and ``s390x``.  Please think carefully (ensure you understand the
previous section) and submit an issue_.  The pattern we have to configure for you
is basically a Python regexp in a format ``owner/project/chroot/package``, e.g.
``@asahi/kernel/.(x86_64|aarch64)/kernel.*``.

.. _Blink: https://en.wikipedia.org/wiki/Blink_(browser_engine)
.. _issue: https://github.com/fedora-copr/copr/issues

Admin SOP
---------

Copr maintainers can configure high performance builders through the
``EXTRA_BUILDCHROOT_TAGS`` variable in ``/etc/copr/copr.conf``.
