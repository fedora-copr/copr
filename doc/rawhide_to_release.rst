.. _rawhide_to_release:

Rawhide to release
==================

When new Fedora is released, we may want to add new chroot in Copr for it. This can be done running the following commands on copr-frontend machine::

    cd /usr/share/copr/coprs_frontend/
    python manage.py create_chroot <name>

Such chroot is empty and does not contain any built packages. Therefore users of the new release will fail to install them. 

That is why we may want to copy the newest version of built packages from rawhide chroot to newly created chroot::

    python manage.py rawhide_to_release <rawhide-chroot> <newly-created-chroot>

This command will also check-on the <newly-created-chroot> in all Copr projects which builds for rawhide.
