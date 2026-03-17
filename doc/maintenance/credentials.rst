.. _fedora_credentials:

Fedora Copr credentials
=======================

The point of this document is to guide Fedora Copr administrators through the
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

Secret variables live in ``/srv/private/ansible/vars.yml`` (private git checkout
on batcave).  Secret files live under ``/srv/private/ansible/files/copr/``.


SSH access to our systems
-------------------------

Anyone who is in the ``sysadmin-copr`` group can `ssh-as-root
<https://github.com/fedora-copr/copr/issues/3003>`_ onto our systems, together
with explicit administrators mentioned in the `root_auth_users`_ config option.
Users' keys are automatically added into ``/root/.ssh/authorized_keys`` when the
corresponding `playbook is run <how_to_upgrade_persistent_instances>`_.

Current ``root_auth_users`` (defined in ``inventory/group_vars/copr_aws``
and ``copr_dev_aws``):

- msuchy
- frostyx
- praiskup
- nikromen


Group membership
----------------

- `FAS copr-sig`_ group, aka the ``copr-team@redhat.com`` e-mail

    The e-mail is just an alias (proxy to team members' INBOXes, not a mailing
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
    role (API token of that role is stored on Fedora Copr Backend, and is
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


Secret variables
----------------

All variables below are defined in ``/srv/private/ansible/vars.yml``.

Most of the job is done by the ./doc/maintenance/generate-secrets.sh script.
It will generate all the secrets for the current date and put them in a new directory.

All the steps required next are described in the README.md file in the generated directory.

You will need to fill some of the values/fields manually, or some are completely
external to the automation process (exactly what is listed by the script).

For those steps (or for verification purposes), here is every secret listed
with a short description of what it is used for and how to rotate it.

Frontend secrets
~~~~~~~~~~~~~~~~

- **Flask SECRET_KEY** — ``{{ copr_secret_key }}``

    Used for CSRF protection and session signing on the frontend
    (``roles/copr/frontend/templates/copr.conf``).

    **Rotate:**

    1. Generate a new key: ``pwgen 60 1``
    2. Update ``copr_secret_key`` in private vars
    3. Run frontend playbook for both prod and staging

    .. warning::

        Rotating this invalidates all existing user sessions.

- **OIDC client secret** — ``{{ copr_oidc_prod_client_secret }}``
  and ``{{ copr_oidc_stg_client_secret }}``

    OIDC client secret for Fedora IdP authentication on frontend
    (``roles/copr/frontend/templates/copr.conf``).

    **Rotate:** Coordinate with the Fedora IdP team to regenerate the client
    secret.  Update private vars and run the frontend playbook.


Frontend / Backend / DistGit shared secrets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **FE/BE Token** — ``{{ copr_backend_password }}``
  (also ``{{ copr_backend_password_dev }}``,
  ``{{ copr_backend_password_stg }}``)

    Token for ``Frontend <-> Backend <-> DistGit`` authentication.  Used as
    ``BACKEND_PASSWORD`` in frontend config and ``frontend_auth`` in backend
    and dist-git configs.

    **Rotate:**

    1. Generate a new password: ``pwgen 60 1``
    2. Update the corresponding variable in private vars
    3. Run ``frontend``, ``backend`` and ``distgit`` playbooks
    4. Test a build

    .. warning::

        Brief communication hiccups may occur during rotation.  Services
        should recover automatically within a few minutes.

- **Sentry DSN** — ``COPR_SENTRY_DSN``

    Data Source Name for Sentry error tracking, used by frontend
    (``coprs/__init__.py``), backend (``copr-be.conf`` — ``sentry_dsn``),
    and dist-git.

    **Rotate:**

    1. Go to `Client Keys for the internal-copr Sentry project
       <https://red-hat-it.sentry.io/settings/projects/fedora-copr/keys/>`_
    2. Delete all existing keys
    3. Click **"Generate New Key"**
    4. Update the DSN in the Fedora Infra secrets repository
    5. Run playbooks for every host (frontend, backend, dist-git)



Backend secrets
~~~~~~~~~~~~~~~

- **AWS Cloud access** — ``{{ copr_aws_access_key_id }}``
  and ``{{ copr_aws_secret_access_key }}``

    AWS credentials used by Resalloc to spawn EC2 builder instances
    (``roles/copr/backend/templates/aws-credentials``,
    ``roles/copr/backend/templates/provision/aws_cloud_vars.yml.j2``).

    **Rotate:**

    1. ``aws --profile fedora-copr iam create-access-key``
    2. Update private vars
    3. Run playbook against both prod and staging backend
    4. ``aws --profile fedora-copr iam delete-access-key --access-key-id <old_id>``

- **IBM Cloud access** — ``{{ copr_cloud_ibm_token }}``

    IBM Cloud API key for spawning s390x builders via Resalloc.  Deployed to
    ``/var/lib/resallocserver/.ibm-cloud-token`` on copr-backend
    (``roles/copr/backend/tasks/resalloc.yml``).

    **Rotate:** In IBM Cloud web-UI, go to "Manage" → "Access (IAM)" →
    "My IBM Cloud API keys" → "Create +" a new key.  Update private vars, run
    both prod and staging backend playbooks, then remove the old key.

- **OSUOSL (OpenStack) access** — ``{{ copr_openstack_osuosl_org_password }}``

    OpenStack password for the OSUOSL project (Power builders).  Used in
    ``roles/copr/backend/templates/provision/rc-osuosl.sh.j2``.

    **Rotate:** Go to the top-right corner of the web-console, hit the
    ``coprteam`` account icon, then go to ``Settings`` → ``Change Password``.
    Then run the backend playbook.

    .. warning::

        This change has an immediate effect.  Open
        ``/var/lib/resallocserver/provision/.rc-osuosl.sh`` on copr-backend in
        advance so you can modify the file as quickly as possible. Or play
        playbooks immediately after the password change.

- **Red Hat Subscription** — ``{{ copr_red_hat_subscription_offline_token }}``,
  ``{{ copr_rhsm_activation_key }}``

    RHSM credentials used for registering build VMs
    (``roles/copr/backend/tasks/main.yml``,
    ``roles/copr/backend/templates/provision/vars.yml.j2``,
    ``roles/copr/backend/files/provision/provision_builder_tasks.yml``).

    **Rotate:**

    1. Generate new offline token at https://access.redhat.com/management/api
    2. Create new activation key if needed in RHSM
    3. Update private vars
    4. Run backend playbook

- **Copr ping bot** — ``{{ copr_ping_bot_login }}``
  and ``{{ copr_ping_bot_token }}``

    Copr API token for the periodic health-check "ping" builds
    (``roles/copr/backend/tasks/copr-ping.yml``).

    **Rotate:**

    1. Log into Copr as the ping bot user
    2. Regenerate the API token in Settings
    3. Update private vars
    4. Run backend playbook

- **UptimeRobot API key** — ``{{ copr_uptimerobot_api_key_ro }}``

    Read-only API key for CDN monitoring
    (``roles/copr/frontend/templates/copr-cdn-check.py.j2``).

    **Rotate:** Regenerate in the UptimeRobot dashboard.  Update private vars
    and run the frontend playbook.

- **Root passwords** — ``{{ copr_root_passwords }}``

    Root passwords per deployment/machine type
    (``roles/copr/pre/tasks/main.yml``).

    **Rotate:** Generate new password, update private vars, run the relevant
    playbook (crypt(3) SHA-512 hashes are used).


Secret files
------------

All files below live under ``/srv/private/ansible/files/copr/`` on batcave.

- **SSH key to builders** — ``buildsys.{prod,devel}.priv``

    Private key used to control builders (running build commands from Backend on
    Builders).  The corresponding public key is in
    ``roles/copr/backend/files/provision/files/buildsys.{prod,devel}.pub``.

    Both ``copr`` and ``resalloc`` users on ``copr-backend`` use it.  ``copr``
    user to perform remote builds, ``resalloc`` to prepare VMs (remote "root"
    access) and to start machines on hypervisors (virsh over ssh).

    **Rotate:**

    1. ``ssh-keygen -t rsa -b 4096 -f /tmp/buildsys``
    2. Replace ``{{ private }}/files/copr/buildsys.{prod,devel}.priv`` on batcave
    3. Replace ``roles/copr/backend/files/provision/files/buildsys.{prod,devel}.pub`` in repo
    4. Update AWS keypairs in all relevant regions::

        aws --profile fedora-copr ec2 delete-key-pair --key-name <name>
        aws --profile fedora-copr ec2 import-key-pair --key-name <name> \
            --public-key-material fileb:///tmp/buildsys.{prod,devel}.pub

    5. Run backend + hypervisor playbooks
    6. Wait for old builders to recycle (or force-remove them)

    .. warning::

        After rotation, copr-backend loses control over all builders that were
        spawned so far.  They will be automatically recycled within minutes.

    .. note::

        This key is overused (builders, hypervisors, resalloc).  It deserves a
        split into multiple keys to simplify rotation.

- **SSL keys using LetsEncrypt**

    For copr backend, we "backup" our currently issued LetsEncrypt certificates
    and keys on Batcave.  This simplifies life while migrating the Backend role
    from one infrastructure machine to another.  These files are not stored in
    ``ansible-private.git`` though.

- **Private key for Keygen** — ``keygen/backup_key.asc``

    GPG public key used to encrypt keygen backups
    (``roles/copr/keygen/tasks/setup_backup.yml``).

    **Rotate:** Only if the backup key is compromised or expires.
    **TODO:** We should probably start using sub-keys to ease rotation.

- **Pulp client certificates** — ``pulp/copr-pulp-{prod,stg}.{crt,key}``

    Client certificate and key for Pulp content API
    (``roles/copr/backend/tasks/pulp.yml``).

    **Rotate:** Coordinate with the Pulp / console.redhat.com team.

- **Pulp registry token** — ``{{ copr_prod_pulp_password }}``
  and ``{{ copr_dev_pulp_password }}``

    Service account token for the `Red Hat Terms-Based Registry`_ used by
    Pulp on backend (``roles/copr/backend/templates/pulp-cli.toml``).
    Corresponding usernames: ``copr_prod_pulp_username`` /
    ``copr_dev_pulp_username``.

    **Requirements:**

    - *Permissions:* FrostyX (or a new service account owner) with authority
      to regenerate tokens on access.redhat.com.
    - *Infrastructure:* praiskup (or another ``sysadmin-main`` member) to
      modify ``ansible-private.git``.

    **Rotate:**

    1. Schedule a short "no-builds" outage (backend/pulp results will remain
       hosted).  Coordinate with FrostyX to estimate the required duration.
    2. FrostyX navigates to the `Red Hat Terms-Based Registry`_, selects the
       appropriate service account (``copr-be`` or ``copr-be-stage``), and
       clicks **Regenerate** for the associated token.
    3. FrostyX securely hands the new token to praiskup, who updates
       ``copr_prod_pulp_password`` or ``copr_dev_pulp_password`` in
       ``ansible-private.git``.
    4. Run the backend playbook to deploy.

    **Special case — new service account:**

    If a completely new service account must be generated (e.g. when FrostyX
    is unavailable **and** there is an actual security incident forcing
    immediate rotation):

    a. Invalidate the old service account (likely requires a support ticket).
    b. Update ``copr_prod_pulp_username`` or ``copr_dev_pulp_username``
       accordingly in the private repository.

    .. warning::

        Do not create a new service account for convenience alone.  Always
        prefer regenerating the token on the existing account (Plan A) unless
        there is a genuine emergency.

.. _`Red Hat Terms-Based Registry`: https://access.redhat.com/terms-based-registry/

- **Fedora Messaging certificates**

    Client certificates for AMQP messaging, used by frontend and backend
    (``roles/copr/frontend/templates/fedora-messaging/copr_messaging.toml``).
    Managed by the ``messaging/base`` role from
    ``/srv/private/ansible/files/rabbitmq/``.

    **Rotate:** Managed by the Fedora Infrastructure messaging team.


Network access controls
-----------------------

- **Keygen (signing server)** — HTTP and signd ports (80, 5167) are firewalled
  to allow connections only from backend IPs.

  These IPs are hardcoded in ``inventory/group_vars/copr_keygen_aws`` and
  ``copr_keygen_dev_aws``.  They must be updated when backend IPs change.

- **PostgreSQL** — ``copr-fe`` user, localhost only (md5 auth via
  ``pg_hba.conf``).

- **Redis** — used by copr-backend, no authentication configured.


Rotation checklist
------------------

1. Go through all the secret variables and files mentioned above and rotate
   them.

2. Take a look at the Bitwarden account and rotate all credentials there, each
   entry should self-document itself.

3. Revise the membership in the groups above.  In particular check:

   - ``root_auth_users`` in ``inventory/group_vars/copr_aws`` — do all listed
     users still need root SSH access?
   - `FAS sysadmin-copr`_ — are all members still active?
   - `FAS aws-copr`_ — are all members still active?
   - `GitHub fedora-copr/copr-team`_ — are all members still active?

4. Verify keygen firewall rules match current backend IPs.


.. _`Ansible SOP`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/ansible/
.. _`sysadmin-main FAS group`: https://accounts.fedoraproject.org/group/sysadmin-main/
.. _`root_auth_users`: https://pagure.io/fedora-infra/ansible/blob/main/f/inventory/group_vars/copr_aws
.. _`FAS aws-copr`: https://accounts.fedoraproject.org/group/aws-copr/
.. _`FAS gitcopr`: https://accounts.fedoraproject.org/group/gitcopr/
.. _`FAS copr-sig`: https://accounts.fedoraproject.org/group/copr-sig/
.. _`FAS sysadmin`: https://accounts.fedoraproject.org/group/sysadmin/
.. _`FAS sysadmin-copr`: https://accounts.fedoraproject.org/group/sysadmin-copr/
.. _`Copr repo`: https://github.com/orgs/fedora-copr/copr
.. _`GitHub fedora-copr/copr-team`: https://github.com/orgs/fedora-copr/teams/copr-team
