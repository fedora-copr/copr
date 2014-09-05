To build documentation locally just run
    make html

To publish new version to the https://readthedocs.org (RTHD), you need:
    1. commit && push your changes into the Copr git
    2. request documentation rebuild by sending POST request to the web hook
       curl -X POST http://readthedocs.org/build/python-copr
