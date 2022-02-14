Copr Buildsystem
================

Copr is designed to be a lightweight buildsystem that allows contributors to create packages, put them in repositories, and make it easy for users to install the packages onto their system. Within the Fedora Project it is used to allow packagers to create third party repositories.


Content
-------

.. toctree::
   :maxdepth: 2

   user_documentation
   release_notes
   developer_documentation
   maintenance_documentation
   downloads
   brainstorming
   features

The main subsections of this wiki: 

* :ref:`user_documentation`: Learn more about how to use Copr. Quick tutorial, FAQ.
* :ref:`developer_documentation`: Learn how to work on and build Copr, and how Copr is put together.
* :ref:`downloads`: Find out how to check out the source code and get RPM releases.
* :ref:`brainstorming`: Some ideas that might end up in the roadmap. Just a page to collect them.
* :ref:`features`: An index page of ideas that have graduated from the :ref:`brainstorming` to become features.

.. _communication:

Communication
-------------

Copr is discussed on #fedora-buildsys on libera.chat

Copr also has a mailing list for discussion: copr-devel@lists.fedorahosted.org `(signup) <https://fedorahosted.org/mailman/listinfo/copr-devel>`_ `(archives) <https://lists.fedorahosted.org/archives/list/copr-devel@lists.fedorahosted.org/>`_

Source
------

Copr comes in several pieces.  You can browse the source here:

* The source for Copr itself: https://pagure.io/copr/copr

Instances
---------

* https://copr.fedorainfracloud.org/ (preferred)
* http://copr.stg.fedoraproject.org/ (staging instance, broken most of the time).

Need To Edit This Wiki?
-----------------------

All the sources for this wiki are placed in our repository at https://pagure.io/copr/copr/ in "doc" directory. If you have commit rights,
then you can to directly edit the files and then follow procedure described here: https://docs.pagure.org/pagure/usage/using_doc.html to
push the modified html files into the docs repo. Even without commit rights, you can contribute. Just send us the patch of the modified
doc files and we will apply it for you (see :ref:`patch_process`).

Want to File a Bug/RFE?
-----------------------

* `Search for bugs here <https://bugzilla.redhat.com/buglist.cgi?bug_status=NEW&bug_status=ASSIGNED&bug_status=POST&bug_status=MODIFIED&bug_status=ON_DEV&bug_status=ON_QA&bug_status=VERIFIED&bug_status=RELEASE_PENDING&classification=Community&list_id=2091774&product=Copr&query_format=advanced>`_: If it has, feel free to add yourself to Cc list of that bugzilla and add comments with more details, logs, etc.
* `Report a new bug <https://bugzilla.redhat.com/enter_bug.cgi?product=Copr>`_: If it has not, then please report it here with all the detail you can muster.
* `Get a Bugzilla account <https://bugzilla.redhat.com/createaccount.cgi>`_: You will need an account in bugzilla to add comments or file new bugzillas.
