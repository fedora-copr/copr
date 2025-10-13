.. _utilities:

Helper Functions
================

The copr.v3 module provides several utility functions that make working with builds and other operations more convenient.

wait function
-------------

The ``wait`` function allows you to wait for builds to complete before continuing execution.

.. autofunction:: copr.v3.wait

Usage Example
~~~~~~~~~~~~~

.. code-block:: python

    from copr.v3 import Client, wait

    # Create a client
    client = Client.create_from_config_file()

    # Submit builds
    build1 = client.build_proxy.create_from_file("@user", "project", "/path/to/file.src.rpm")
    build2 = client.build_proxy.create_from_url("@user", "project", "http://example.com/package.src.rpm")

    # Wait for both builds to finish
    finished_builds = wait([build1, build2])

    # Check the results
    for build in finished_builds:
        print(f"Build {build.id} finished with state: {build.state}")

With Callback
~~~~~~~~~~~~~

You can provide a callback function to monitor progress:

.. code-block:: python

    from copr.v3 import Client, wait

    def progress_callback(builds):
        for build in builds:
            print(f"Build {build.id}: {build.state}")

    client = Client.create_from_config_file()
    build = client.build_proxy.create_from_file("@user", "project", "/path/to/file.src.rpm")
    
    # Wait with progress updates every 30 seconds
    wait(build, callback=progress_callback)

With Timeout
~~~~~~~~~~~~

You can set a timeout to avoid waiting indefinitely:

.. code-block:: python

    from copr.v3 import Client, wait
    from copr.v3.exceptions import CoprException

    client = Client.create_from_config_file()
    build = client.build_proxy.create_from_file("@user", "project", "/path/to/file.src.rpm")
    
    try:
        # Wait for maximum 1 hour (3600 seconds)
        wait(build, timeout=3600)
        print("Build completed within timeout")
    except CoprException as e:
        if "Timeouted" in str(e):
            print("Build timed out")
        else:
            raise
