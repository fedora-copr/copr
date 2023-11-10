.. _fedora_credentials:

Fedora Copr credentials
=======================

The point of this document is to guide Fedora Copr admininstrators through the
list of credentials Fedora Copr uses, and documenting how to maintain and rotate
them.


Basic info
----------

All automation-related credentials are stored in ``ansible-private GIT``, as
documented in the `Ansible SOP`_.  This repo is not visible anywhere to give you
a link.  Only `sysadmin-main FAS group`_ folks have permissions to read and
modify the repository (for Copr related stuff, ping ``praiskup``).

Fedora Copr team folks can only access a subset of stored credentials (with a
subset of available playbooks) through the ``rbac-playbook`` wrapper.

.. note::

   There's the `AWX proposal`_ which will probably make this
   credential-handling processes much more granular and convenient, perhaps
   together with `Vault proposal`_.


SSH access to our systems
-------------------------

Anyone who is in the ``sysadmin-copr`` group can `ssh-as-root
<https://github.com/fedora-copr/copr/issues/3003>`_ onto our systems, together
with explicit administrators mentioned in the `root_auth_users`_ config option.
Users' keys are automatically added into ``/root/.ssh/authorized_keys`` when the
corresponding `playbook is run <how_to_upgrade_persistent_instances>`_.


Group membership
----------------

- `FAS copr-sig`_ group, aka the ``copr-team@redhat.com`` e-mail

    The e-mail is jus alias (proxy to team members' INBOXes, not a mailing
    list), and the group is receiving various reports related to Fedora Copr
    operation (e.g. crontab e-mails, Nagios reports, etc.).

    Members of this group are also assigned as the "default assignee" to various
    Fedora components related to Copr.  Bug reports are automatically delivered
    to that e-mail.

- `FAS sysadmin-copr`_ group, aka ``copr-devel@lists.fedorahosted.org`` e-mail

    Members in this group are able to execute Fedora Copr related playbooks (SSH
    to Batcave machine, and run them there).  Members of this group can also SSH
    to all of Fedora Copr hypervisors (as root).  Members can't modify
    playbooks, for this the ``sysadmin`` membership is needed, too.

- `FAS sysadmin`_ group

    This group allows Fedora Copr members to commit (merge PRs) into the
    `Ansible git repo <Ansible SOP>`_.


- `FAS gitcopr`_ group

    This used to be a list of users being able to commit to Copr, but not
    anymore. Newly it is just a list of users being able to maintain the
    `@copr <https://copr.fedorainfracloud.org/groups/g/copr/coprs/>`_ group in
    the Fedora Copr instance.

- `FAS aws-copr`_ group

    List of users that are able to log into AWS console (using FAS OpenID) and
    maintain/fix EC2 resources (access VM console, maintain volumes, etc.).  The
    real production VMs should never be started by humans but the ``copr`` EC2
    role (API token of that role is used stored on Fedora Copr Backend, and is
    used to spawn VMs automatically, see below the *AWS Cloud access* section).

- `GitHub fedora-copr/copr-team`_

    This is the group of upstream Copr.  Members have the rights to merge
    pull-requests in the main `Copr repo`_.

- `Pagure @copr group <https://pagure.io/group/copr>`_

    Members of this group maintain the projects in the `@copr pagure.io
    namespace <https://pagure.io/projects/copr/%2A>`_ and several other
    projects.


Bitwarden account
-----------------

Folks in Copr Team use a Bitwarden account where they store other passwords that
are not strictly related to automation (mailing list passwords, stuff related to
manual release processes, etc.).  Ask ``copr-team@redhat.com`` if you believe
you need something from there.


General secret variables
------------------------

The variables are defined in ``/srv/private/ansible/vars.yml`` (private git
checkout on batcave).

- **IBM Cloud access**

    The ``{{ ibmcloud_token_file }}`` file is created on ``copr-backend`` to
    allow spawning VMs in IBM Cloud (by Resalloc).  It is defined by **secret
    variable** ``{{ copr_cloud_ibm_token }}``.

    **Rotate:** In web-UI, go to "Manage", then "Access (IAM)" then
    "My IBM Cloud API keys" and "Create +" a new key.  Run playbook against both
    production and staging Backend, and remove the old one.

- **AWS Cloud access**

    There are two **secret variables**, ``{{ copr_aws_access_key_id }}`` and
    ``{{ copr_aws_secret_access_key }}`` which we use to templatize
    the ``$HOME/.aws/config`` files.

    **Rotate**::

        1. aws --profile fedora-copr iam create-access-key
        2. run playbook against both {prod,dev} backend
        3. aws --profile fedora-copr iam delete-access-key --access-key-id <old_id>

- **OSUOSL (OpenStack) access**

    There's ``{{ copr_openstack_osuosl_org_password }}`` used in
    ``rc-osuosl.sh.j2`` template.

    **Rotate**::  TODO. We are using ``name+password`` but we should start
    using some API token (once OSUOSL OpenStack allows us to visit
    ``/identity/application_credentials/`` URL).

    .. warning::

        There's no time to distribute the credential to private.git, and run
        playbooks.  This change has an immediate effect; so it is better to open
        the ``/var/lib/resallocserver/provision/.rc-osuosl.sh`` on copr-backend
        in advance in terminal so you can modify the file as quickly as
        possible.

    Just go to the top-right corner of web-console, hit the ``coprteam`` acount
    icon, then go to ``Settings``, and ``Change Password``.  Then run the
    backend playbook.


- **Copr FE/BE Token**

    There's the ``{{ copr_backend_password }}`` secret variable that is used on
    several places.  It is used for ``Frontend <-> Backend <-> DistGit``
    authentication

    **Rotate** by just changing the credential, and then running ``frontend``,
    ``backend`` and ``distgit`` playbooks.


Secret files
------------

- **SSH Key to builders**

    There's the ``{{ private }}/files/copr/buildsys.priv`` file on Batcave.
    This is the private key that we use to control our builders (running build
    commands from ``Backend`` on ``Builders``).

    **Rotate** **TODO** Unfortunately, we overuse it on too many places.  Both
    ``copr`` and ``resalloc`` users on ``copr-backend`` use it.  ``copr`` user
    to perform the remote builds, ``resalloc`` to prepare VMs (remote "root"
    access) and to actually start machines on hypervisors (virsh over ssh).
    This deserves a split to multiple keys to simplify the rotation work.

- **SSL Keys using letsencrypt**

    For copr backend, we "backup" our currently issued LetsEncrypt certificates
    and keys on Batcave, this is to simplify our life while migrating the
    Backend role from one infrastructure machine to another (moving from
    ``Fedora N`` to ``Fedora N+2`` typically.  These files are not stored in
    ``ansible-private.git`` though.

- **Private key for Keygen**

    There's the ``{{ private }}/files/copr/keygen/backup_key.asc`` file, the
    main private key for Fedora Copr keygen.

    **Rotate**: TODO: We should probably start using sub-keys to ease rotation.


Rotation instructions
---------------------

1. Go through all the secret variables and files mentioned above and rotate
   them.

2. Take a look at the Bitwarden acount and rotate all credentials there, each
   entry should self-document itself.

3. Revise the membership in the groups above.

.. _`Ansible SOP`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/ansible/
.. _`infra issues`: https://pagure.io/fedora-infrastructure/new_issue
.. _`AWX proposal`: https://pagure.io/fedora-infrastructure/issue/11377
.. _`Vault proposal`: https://pagure.io/fedora-infrastructure/issue/11612
.. _`sysadmin-main FAS group`: https://accounts.fedoraproject.org/group/sysadmin-main/
.. _`root_auth_users`: https://pagure.io/fedora-infra/ansible/blob/main/f/inventory/group_vars/copr_aws
.. _`FAS aws-copr`: https://accounts.fedoraproject.org/group/aws-copr/
.. _`FAS gitcopr`: https://accounts.fedoraproject.org/group/gitcopr/
.. _`FAS copr-sig`: https://accounts.fedoraproject.org/group/copr-sig/
.. _`FAS sysadmin`: https://accounts.fedoraproject.org/group/sysadmin/
.. _`FAS sysadmin-copr`: https://accounts.fedoraproject.org/group/sysadmin-copr/
.. _`Copr repo`: https://github.com/orgs/fedora-copr/copr`
.. _`GitHub fedora-copr/copr-team`: https://github.com/orgs/fedora-copr/teams/copr-team
