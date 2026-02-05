.. _development_versions:

How to Maintain Package Versions
================================

Sometimes, typically when proposing a change (e.g., modifying the Backend
↔ Frontend protocol, or adding new methods into the
``python3-copr-common`` package that other packages depend on), we need to
specify version constraints between our components to avoid
misinstallations.  Below are a few documented scenarios.


Package Update Time a.k.a. TL;DR
--------------------------------

Most dependency checks are enforced by ``Requires`` in package versions.  When
updating the system, you generally do not need to worry about these, as the
package manager prevents invalid configurations.  However, some checks occur at
runtime.

The runtime protection hierarchy follows a ``frontend -> backend <- rpmbuild``
pattern.  In this model, the backend drives critical runtime checks; if the
frontend or the builder is too old for a specific backend version, the backend
will "hang" and wait for them to be updated.

In practice, this means that whenever you update the system with a backward-
incompatible change in the inter-component API, you must follow a "shutdown ->
upgrade -> restart" workflow targeting the **backend component first**.


Changing the Frontend ↔ Backend Protocol
----------------------------------------

There are two relevant values: ``MIN_FE_BE_API`` (backend side) and
``Copr-FE-BE-API-Version`` (frontend side).

Whenever the backend detects that the Frontend counterpart is older than
expected, it delays processing.  Please bump the value anytime you think
it's warranted, there's no risk in doing so, but forgetting to update it is
risky (backend would process incompatible requests).

To ensure smooth upgrades, always update the ``copr-backend`` machine
first, so it is ready (after re-deployment) and waiting for the updated &&
fully-compatible Frontend.


Changes in Backend ↔ Builder Protocol
-------------------------------------

Whenever the Backend attempts to hand over a task to a Builder machine, it
verifies the "remote" ``copr-builder`` RPM (sub)package version.  If the version
is lower than ``MIN_BUILDER_VERSION`` (as defined in
``backend/copr_backend/background_worker_build.py``), the Backend marks the
builder machine as unusable, and allocates a new one instead.


Changes in Frontend ↔ Builder Protocol
--------------------------------------

Typically, this involves updating certain ``/backend/`` routes on the Frontend.
This process must be performed in two steps: the runtime dependencies for both
``Frontend ↔ Backend`` and ``Backend ↔ Builder`` (see above) must be bumped
simultaneously.


Changes in python3-copr-common
------------------------------

This package is heavily used by all other components, except for
`python3-copr` (which is intentionally self-contained, see below).  Bumping
its version is not a problem, since other components depend on it with
a ``>=`` constraint.

While we normally ship ``MAJOR.MINOR`` versions of our components, during
development we may need to add a third ``.PATCH`` version component (this
can be done arbitrarily in any pull-request — later, when making a
release, we remove the ``.PATCH`` suffix and bump to either ``MAJOR+1`` or
``MAJOR.MINOR+1``).

Anytime you bump the ``.PATCH`` version, please update the corresponding
``%copr_common_version`` macro in dependent components that you modify.  Also
remember to synchronize the package version in both the
``python-copr-common.spec`` and ``setup.py``.  See this `discussion`_ for more
information.

Handling suffixes like ``dev1`` or ``1post`` is tricky, because RPM and
Python (our main development language stack) compare such versions
differently.


Changes in python3-copr
-----------------------

This is our Python API, so we should be careful when making breaking changes.
The package lives in ``<gitroot>/python/python-copr.spec``.

In general, when bumping versions, follow the same process described above for
``python3-copr-common`` (bump the `.PATCH` version in both ``setup.py`` and the
``python-copr.spec``).

The only difference is that ``copr-cli`` uses a different macro, which you
should bump instead: ``%min_python_copr_version``.

.. _discussion: https://github.com/fedora-copr/copr/pull/3835
