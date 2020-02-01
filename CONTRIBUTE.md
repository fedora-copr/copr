# CONTRIBUTE.md

This document describes coding standards and practices that Copr developers
agreed to comply with. In a case of controversy, the following rules take
precedence over one's personal preference.


## PEP8

All new code must be [PEP8][pep8] compliant. Occasional exceptions to this rule
are allowed only when:

1. The violation is uniformly approved
2. The code contains a comment to disable Pylint warning,
   e.g. ` # pylint: disable=W0703`


## Docstrings

Although PEP8 permits multiple styles of writing docstrings, the standard for
this project is using triple-quotes, e.g.

    """
    This is an example docstring
    having more than just one line
    """

The triple-quote style must be used even for one-line docstrings, e.g.

    """Return the pathname of the KOS root directory."""


## Primary keys

Every database table must have an autoincrement integer primary key named `id`.
This applies also in cases when the ID value is not used.

A presence of primary key is a requirement for data to comply with the First
normal form. Having numeric primary keys is a convention agreed among team
members.



[pep8]: https://www.python.org/dev/peps/pep-0008/
