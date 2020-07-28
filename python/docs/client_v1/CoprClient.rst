.. warning::
    Legacy client is obsolete, please use Client version 3 instead. :ref:`This document <migration>` describes the migration process.


CoprClient
==========


.. autoclass:: copr.client.client.CoprClient
    :members: create_from_file_config, create_project, get_project_details,
        delete_project, modify_project, get_projects_list,
        create_new_build, get_build_details, cancel_build,
        get_project_chroot_details, modify_project_chroot_details,
        search_projects
