.. _building_package:

Building package
================

First - go to root directory of your copr.git checkout. Then checkout
a particular commit from which you would like to build the packages.

Install `rpkg <https://pagure.io/rpkg-util>`_, render spec files and
install Copr build dependencies::

    sudo dnf install rpkg

    rpkg --path frontend spec --outdir /tmp/rpkg
    sudo dnf builddep /tmp/rpkg/copr-frontend.spec

    rpkg --path backend spec --outdir /tmp/rpkg
    sudo dnf builddep /tmp/rpkg/copr-backend.spec

    rpkg --path cli spec --outdir /tmp/rpkg
    sudo dnf builddep /tmp/rpkg/copr-cli.spec

    rpkg --path selinux spec --outdir /tmp/rpkg
    sudo dnf builddep /tmp/rpkg/copr-selinux.spec

Now you can build the packages themselves::

    cd frontend && rpkg local && cd ..

    cd backend && rpkg local && cd ..

    cd cli && rpkg local && cd ..

    cd selinux && local && cd ..

If you want just src.rpm, run::

    cd frontend && rpkg srpm && cd ..

    cd backend && rpkg srpm && cd ..

    cd cli && rpkg srpm && cd ..

    cd selinux && rpkg srpm && cd ..

If you are developer and want to test your changes, run (don't forget to `cd` to particular package)::

    rpkg local

    # or

    rpkg srpm

For more information see ``man rpkg``.

If you have write access to copr.git, you may create a new release by::

    rpkg tag
