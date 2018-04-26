.. _contribute:

Contribute
==========

Are you familiar with Python? Look at the code and do :ref:`brainstorming` something. When you are done send us a patch.

Did you write some useful script which uses Copr API? Share it with the others on mailing list!

More about coding is in :ref:`developer_documentation`


Local Development Environment
-----------------------------

We support docker-compose to spawn the whole docker stack, including builder, on a local machine:

- `Read the original blog post about COPR docker stack <https://frostyx.cz/posts/copr-stack-dockerized>`_
- `Learn more about docker on Fedora <https://developer.fedoraproject.org/tools/docker/about.html>`_


Spawning the stack
------------------

To start your developer environment, simply run ``docker-compose up`` command in the repository

::

    $ git clone https://pagure.io/copr/copr.git

    $ cd copr

    $ docker-compose up -d

The ``docker-compose up`` command will take several minutes to complete.

You should be now able to access the frontend on http://localhost:5000.


Testing your changes
--------------------

To test your in frontend or backend, you should restart the respective container for the changes to take effect, e.g.:

::

     $ docker-compose restart frontend


Stopping the machines
---------------------

::

    $ docker-compose stop


Removing the machines
---------------------

To remove the machines, run the following command

::

    $ docker-compose rm


Debugging machines
------------------

You can get shell to the e.g. backend container and see the logs

::

    $ docker exec -it docker_backend_1 /bin/bash
    # tail -f /var/log/copr-backend/backend.log

If something went wrong, you can also try to restart all the backend services and see if that helped

::

    # supervisorctl restart all


Unit tests
^^^^^^^^^^

Those tests are accessible directly from COPR pagure repository (https://pagure.io/copr/copr). If you change something in the frontend package, you should run the frontend test suite before committing::

    $ cd copr/frontend

    $ vim coprs_frontend/manage.py      (and make some change)

    $ ./run_tests.sh


Behavioral tests
^^^^^^^^^^^^^^^^

Currently, there are three test-suites: integration, backend and dist-git. Apart from being useful as an actual feature specification, these test suites are also used to verify COPR functionality before making a new release. The following code snippet shows the steps needed run the dist-git test-suite as an example

::

    $ cd copr/beaker-tests/DockerTestEnv    # this is good for running the test in isolation (setup phase installs packages etc.)

    $ make && make run                      # to build and run a test container

    $ make sh                               # to enter the container

    $ cd copr/beaker-tests/Regression/dist-git

    $ ./runtest.sh                          # run the test-suite (this will start with calling the setup.sh script), in the end you should see lots of GREEN checks saying: 'PASS'


Documentation
-------------

We need to document our code, write documentation for users. Do you want to write it?

We need general documentation of Copr. You did not find documentation for the task you are currently doing? Just create a new wiki page and document what it is you did. Some existing documentation is outdated and you may review it and update it.


Help others
-----------

Or you can just hang on IRC or mailing list (see :ref:`communication`) and try to answer questions others may have.
