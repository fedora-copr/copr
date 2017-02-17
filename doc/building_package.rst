.. _building_package:

Building package
================

First - go to root directory of your copr.git checkout.

Install `Tito <https://github.com/dgoodwin/tito>`_ and Copr build dependencies::

    dnf builddep frontend/copr-frontend.spec

    dnf builddep backend/copr-backend.spec

    dnf builddep cli/copr-cli.spec

    dnf builddep selinux/copr-selinux.spec


Now you can build the package itself::

    cd frontend && tito build --rpm && cd ..

    cd backend && tito build --rpm && cd ..

    cd cli && tito build --rpm && cd ..

    cd selinux && tito build --rpm && cd ..


If you want just src.rpm, run::

    cd frontend && tito build --srpm && cd ..

    cd backend && tito build --srpm && cd ..

    cd cli && tito build --srpm && cd ..

    cd selinux && tito build --srpm && cd ..

If you are developer and want to test your changes, commit them and run (don't forget to `cd` to particular package)::

    tito build --test --rpm

    # or

    tito build --test --srpm

For more information see ``man tito``.

If you have write access to copr.git, you may create new release by::

    tito tag
