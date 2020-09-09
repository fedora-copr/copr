.. _sanity_tests:


Running Sanity tests against local dev instance
===============================================

When implementing a new feature, you might be asked to write a beaker-tests for it. Sanity tests are usually run against the copr-fe-dev instance, which is a problem when you don't have access to it. This article describes how to run Sanity tests against the `local docker-compose dev environment <http://frostyx.cz/posts/copr-stack-dockerized>`_.


DockerTestEnv container
-----------------------

Our beaker tests can change the filesystem so we strongly discourage you from running them on your host system. There is a docker container for this purpose. Follow these instructions to building it, running it and executing a shell in it.


::

    # In Copr git repository
    cd ./beaker-tests/DockerTestEnv

    # Build and run the docker container for executing beaker-tests
    make build && make run

    # Join the network created by docker-compose
    # You can skip this step when running tests against
    # copr-fe-dev or another personal instance
    docker network connect copr_default test-env

    # Open a shell in it
    make sh


API token
---------

Now we are going to operate in the container.

::

    # Set your API token and Copr URL
    [root@test-env ~] vim ~/.config/copr

Find the token here `<http://127.0.0.1:5000/api/>`_. Simply remove the existing content of ``~/.config/copr`` and put your token there. The only thing that needs to be changed is ``copr_url``. It should be set this way.

::

    copr_url = http://frontend

We have already connected this container to the network created by docker-compose, so we can communicate with the frontend like this ``curl frontend``.


Running the tests
-----------------

::

    [root@test-env ~] cd ~/copr/beaker-tests/Sanity/copr-cli-basic-operations/

    # To see all the test scripts
    [root@test-env copr-cli-basic-operations] ls *.sh

    # To execute all the sanity tests in parallel
    [root@test-env copr-cli-basic-operations] ./all-in-tmux.sh

    # To execute subset of sanity tests in parallel
    [root@test-env copr-cli-basic-operations] ./all-in-tmux.sh runtest.sh runtest-modules.sh

    # To execute individual test
    [root@test-env copr-cli-basic-operations] ./build-spec.sh
