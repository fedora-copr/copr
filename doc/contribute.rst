.. _contribute:

Contribute
==========

Are you familiar with Python? Look at the code and do :ref:`brainstorming` something. When you are done send us a patch.

Did you write some useful script which uses Copr API? Share it with the others on mailing list!

More about coding is in :ref:`developer_documentation`

Local Development Environment
-----------------------------

We support Vagrant to create frontend and dist-git parts of the local development environment and docker to create the backend (the actual building engine). 

- `Learn more about Vagrant on Fedora <https://developer.fedoraproject.org/tools/vagrant/about.html>`_
- `Learn more about docker on Fedora <https://developer.fedoraproject.org/tools/docker/about.html>`_

Starting the frontend and dist-git
----------------------------------

To start your developer environment, simply run ``vagrant up`` command in the repository::

    $ git clone https://pagure.io/copr/copr.git

    $ cd copr

    $ vagrant up

The ``vagrant up`` command will take several minutes to complete.

You should be now able to access the frontend on http://localhost:5000.

Testing your changes
--------------------

To test your changes in frontend or copr-dist-git, commit them to your local git repo and run ``vagrant reload``::

    $ git add .

    $ git commit -m "my test"

    $ vagrant reload


The ``vagrant reload`` command reboots both machines, builds the copr packages from the actual commit (HEAD) and installs them on the machines.

Stopping the machines
---------------------

::

    $ vagrant halt

Removing the machines
---------------------

To completely remove the machines, run the following command::

    $ vagrant destroy


Build docker backend image
--------------------------

In the cloned backend repository run::

    $ cd backend/docker

    $ make

Run the backend docker image
----------------------------

::

    $ make run


Now, if you have already started frontend and dist-git by using the provided Vagrantfile, you are done and the full COPR stack is running directly on your machine. 
You can try to build something and browse the build results at url http://localhost:5002/results.

Debugging backend
-----------------

You can get shell to the COPR backend container and see the logs::

    $ make sh

    # tail -f /var/log/copr/worker.log

If something went wrong, you can also try to restart all the backend services and see if that helped::

    # supervisorctl restart all

Update backend image and re-run it
----------------------------------

If you make any changes to the backend source and you want to run the new backend version, run the following command in the backend/docker directory::

    $ make update

Note that the changes in the COPR git repo must be **commited** at this point.

Testing
-------

After you develop (or even better before) a sparkling, new feature, it is not a bad idea to ship it with a test. There are two kinds of tests available: unit ones and regression (behavioral) ones.

Unit tests
^^^^^^^^^^

Those tests are accessible directly from COPR pagure repository (https://pagure.io/copr/copr). If you change something in the frontend package, you should run the frontend test suite before committing::

    $ cd copr/frontend

    $ vim coprs_frontend/manage.py      (and make some change)

    $ ./run_tests.sh


Behavioral tests
^^^^^^^^^^^^^^^^

Currently, there are three test-suites: integration, backend and dist-git. Apart from being useful as an actual feature specification, these test suites are also used to verify COPR functionality before making a new release. The following code snippet shows the steps needed run the dist-git test-suite as an example::

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
