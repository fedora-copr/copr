.. warning::
    Client version 2 is obsolete, please use Client version 3 instead.


General
=======

.. autofunction:: copr.create_client2_from_params
.. autofunction:: copr.create_client2_from_file_config


CoprClient
==========


.. autoclass:: copr.client_v2.client.CoprClient
   :members: projects, builds, build_tasks, project_chroots,
      mock_chroots, create_from_file_config, create_from_params, post_init
