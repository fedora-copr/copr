.. _fedora_magazine:

Fedora Magazine
===============

We write `Fedora Magazine <https://fedoramagazine.org/>`_ articles about new
interesting projects in Copr. See all articles related to Copr -
https://fedoramagazine.org/series/copr


RTFM
----

To be able to write an article, some prerequisites are required, please see the
official Fedora Magazine documentation -
https://docs.fedoraproject.org/en-US/fedora-magazine/getting-access/

To write the article, please follow the Fedora Magazine editorial workflow -
https://docs.fedoraproject.org/en-US/fedora-magazine/writing-an-article/


4 cool new projects to try in COPR
----------------------------------

Do not pick projects for a new article by going through the web UI, viewing all
projects, and filtering candidates manually. The pool of new projects can be
narrowed to only the interesting subset of them (around one in fifteen projects)
using `misc/copr_new_packages.py` script.

Print interesting projects for the last month::

    $ python misc/copr_new_packages.py

Print interesting projects since a specified date in a `YYYY-MM-DD` format::

    $ python misc/copr_new_packages.py --since 2020-11-01
