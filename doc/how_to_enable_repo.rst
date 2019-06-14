:orphan:

.. _how_to_enable_repo:

How to enable repo
==================

You have two options to do that:

1. If you're using a version of Linux with dnf::

    # dnf copr enable user/project 

- you need to have dnf-plugins-core installed 

2. or if you have older distribution::

    # yum copr enable user/project 

- you need to have yum-plugin-copr installed 

3. You can download a repo file and place it to /etc/yum.repos.d/

- you can find the file on an Overview page of the project
