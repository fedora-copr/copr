.. _how_to_upgrade_persistent_instances:

How to upgrade persistent instances
===================================

This article describes how to upgrade persistent instances (e.g. copr-fe-dev) to new Fedora version.


Requirements
------------

* an account on `Fedora Infra OpenStack`_
* access to persistent tenant
* ssh access to batcave01


Find source image
-----------------

For OpenStack, there is an image registry on `OpenStack images dashboard`_.  By
default you see only the project images; to see all of them, click on the
``Public`` button.

Search for the ``Fedora-Cloud-Base-*`` images of the particular Fedora. Please note
that if there is a timestamp in the image name suffix than it is a beta version.
It is better to use images with numbered minor version.

The goal in this step is just to find an image name.


Update the image in playbooks
-----------------------------

Once the new image name is known, make sure it is set in `vars/global.yml`, e.g.::

    fedora30_x86_64: Fedora-Cloud-Base-30-1.2.x86_64

Then edit the host vars for the instance::

    vim inventory/host_vars/<instance>.fedorainfracloud.org
    # e.g.
    vim inventory/host_vars/copr-dist-git-dev.fedorainfracloud.org

And configure it to use the new image::

    image: "{{ fedora30_x86_64 }}"

That is all, that needs to be changed in the ansible repository. Commit and push it.


Terminate the instance
----------------------

This is the scary part when the current running and working instance is terminated.
Make sure, that you have enough time, there is no going back.

Open the `OpenStack instances dashboard`_ and switch the current project to ``persistent``
and find the instance, that you want to terminate. Make sure, it is the right one! Don't
mistake e.g. production instance with dev. Then look at the ``Actions`` column and click
``More`` button. In the dropdown menu, there is a button ``Terminate instance``, use it.


Provision new instance from scratch
-----------------------------------

On batcave01 run playbook to provision the instance. For dev, see

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-dev-machines

and for production, see

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-production-machines

.. note:: Please note that the playbook may stuck longer than expected while waiting for a new
          instance to boot. See `Initial boot hangs waiting for entropy`_.


Troubleshooting
---------------

Initial boot hangs waiting for entropy
......................................

Because of a known infrastructure issue `Fedora infrastructure issue #7966`_ initial boot
of an instance in OpenStack hangs and waits for entropy. It seems that it can't be fixed
properly, so we need to workaround by going to `OpenStack instances dashboard`_, opening
the instance details, switching to the ``Console`` tab and typing random characters in it.
It resumes the booting process.



.. _`Fedora Infra OpenStack`: https://fedorainfracloud.org
.. _`OpenStack images dashboard`: https://fedorainfracloud.org/dashboard/project/images/
.. _`OpenStack instances dashboard`: https://fedorainfracloud.org/dashboard/project/instances/
.. _`Fedora infrastructure issue #7966`: https://pagure.io/fedora-infrastructure/issue/7966
