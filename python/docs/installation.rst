Installation
============

Dependencies:
-------------
::

 python2.6+
 python-requests
 python-six

repo
----
Available for fedora 21+
::

    dnf install python-copr python-copr-doc

source
------

.. code-block:: bash

    git clone https://pagure.io/copr/copr.git
    cd python
    # enable virtualenv if needed
    pip install -r requirements.txt
    python setup.py install
