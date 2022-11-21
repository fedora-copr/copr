How do we build in Copr
=======================

This is a temporary solution, till we have the [Packit monorepo
support](https://github.com/packit/packit/issues/1505).

There's the `.github/workflows/copr-builds.yml` workflow file.  This calls the
`.github/copr-build-helpers/changed-packages` helper which provides a list of
changed packages in the JSON format, and using that generates a list of jobs to
be executed.

Because we use the Copr custom method, we need to configure the Copr side first.
For this, there's a set of scripts in the `.github/copr-builds-helpers` helpers
that are supposed to be executed from time to time by anyone from the Fedora
Copr `@copr` group.
