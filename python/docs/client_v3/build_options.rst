Build Options
=============

When submitting a new build, it is possible to specify some options in `buildopts` parameter.
Those are common for all build methods.

==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
timeout             int                  build timeout
memory              int                  amount of required memory for build process
chroots             list of strings      build only for given chroots
background          bool                 mark the build as a background job
progress_callback   callable             function that receives a ``MultipartEncoderMonitor`` instance for each chunck of uploaded data
==================  ==================== ===============


Example usage
-------------

.. code-block:: python

    url = "http://foo.ex/baz.src.rpm"
    client.build_proxy.create_from_url(url, buildopts={
        "chroots": ["fedora-rawhide-x86_64"],
        "background": True,
    })
