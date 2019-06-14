:orphan:

.. _SrcRpmUpload:

Upload of src.rpm
=================

Problem
-------

Right now user must upload src.rpm somewhere on his web site and he provide URL where his src.rpm reside. Backend will download the package from this URL. But not everybody have place, where he can easily upload src.rpm. We should provide user option to upload src.rpm.

Requirements
------------

- In copr.conf and config.py create new variables:

  - SRC_UPLOAD_DIR - directory where uploaded files be stored.
  - SRC_UPLOAD_URL - URL under which is SRC_UPLOAD_DIR accessible from internet over http protocol.

- add to the page /detail/msuchy/copr/add_build/ option to upload src.rpm
- if file is uploaded, it will be stored in SRC_UPLOAD_DIR

  - Note that it is possible that two users use the same name for different content. We should probably store it in SRC_UPLOAD_DIR/<SHA1sum>/<Name_of_file>
  - Store this URL (SRC_UPLOAD_URL + <SHA1sum>/<Name_of_file>) into pkgs of build table.

- Frontend code must not open the file as rpm. I.e. parse meta information from the file. We must interpret is as pure binary file.
- We should give user some quota and reject upload if he is over quota.
- We should give user ability to delete old unused uploads.

Owner
-----

TBD

User documentation
------------------

TBD
