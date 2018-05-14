Package Source Type
===================

Read more about source types in the
`user documentation <https://docs.pagure.org/copr.copr/user_documentation.html#build-source-types>`_.


SCM
---

Parameters when ``source_type_text=scm`` is used.
See `User Documentation <https://docs.pagure.org/copr.copr/user_documentation.html#scm>`_ for more information.

=====================  ==================== ===============
Field                  Type                 Description
=====================  ==================== ===============
clone_url              str
committish             str
subdirectory           str
spec                   str
scm_type               str                  "git", "svn"
srpm_build_method      str                  See `User documentation <https://docs.pagure.org/copr.copr/user_documentation.html#scm>`_ for more info
=====================  ==================== ===============


Rubygems
--------

Parameters when ``source_type_text=rubygems`` is used.
See `User Documentation <https://docs.pagure.org/copr.copr/user_documentation.html#rubygems>`_ for more information.

==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
gem_name            str
==================  ==================== ===============


PyPI
----

Parameters when ``source_type_text=pypi`` is used.
See `User Documentation <https://docs.pagure.org/copr.copr/user_documentation.html#pypi>`_ for more information.

=====================  ==================== ===============
Field                  Type                 Description
=====================  ==================== ===============
pypi_package_name      str
pypi_package_version   str
python_versions        list of int
=====================  ==================== ===============


Custom
------

Parameters when ``source_type_text=custom`` is used.
See `User Documentation <https://docs.pagure.org/copr.copr/custom_source_method.html#custom-source-method>`_ for more information.

=====================  ==================== ===============
Field                  Type                 Description
=====================  ==================== ===============
script                 str
builddeps              str
resultdir              str
chroot                 str
=====================  ==================== ===============


Example Usage
-------------

.. code-block:: python

    client.package_proxy.add("@copr", "foo", "mypackage",
                             source_type_text="rubygems",
                             source_dict={"gem_name": "mygem"})
