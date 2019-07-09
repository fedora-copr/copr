# Copyright (C) 2019  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Private hierarchy of Copr messages.  This is for module-internal purposes only.
"""

from fedora_messaging import message

class _CoprMessage(message.Message):
    def __init__(self, *args, **kwargs):
        if 'body' in kwargs:
            body = kwargs.pop('body')
            if 'msg' in body:
                body = body['msg']
            kwargs['body'] = body

        super(_CoprMessage, self).__init__(*args, **kwargs)

    """
    Base class that all Copr messages should inherit from.
    """
    def __str__(self):
        return "Unspecified Copr message"

    def _str_prefix(self):
        return "Copr Message"


class _CoprProjectMessage(_CoprMessage):
    def _str_prefix(self):
        return '{0} in project "{1}"'.format(
            super(_CoprProjectMessage, self)._str_prefix(),
            self.project_full_name,
        )

    @property
    def project_owner(self):
        """
        Owner name of the Copr project.  It may be either ``@groupname`` or
        ``username`` (leading `at` sign indicates group).
        """
        raise NotImplementedError

    @property
    def project_name(self):
        """
        Name of the copr project.  Note that several owners may host project of
        the same name at the same time.
        """
        raise NotImplementedError

    @property
    def project_full_name(self):
        """
        Project owner name + project name, separated by slash.
        """
        return '{0}/{1}'.format(self.project_owner, self.project_name)


class _BuildMessage(_CoprProjectMessage):
    def _str_prefix(self):
        return '{0}: build {1}'.format(
            super(_BuildMessage, self)._str_prefix(),
            self.build_id,
        )

    @property
    def build_id(self):
        """
        Copr Build ID.

        Note that one copr build (identified by this ID) generates several build
        messages (namely for each :py:attr:`.chroot`, before build started and
        after the build finished).
        """
        raise NotImplementedError

    @property
    def package_name(self):
        """
        *Name* of the *package* this message is related to
        [#footnote_may_be_unknown]_.
        """
        raise NotImplementedError

    # TODO: from old messages, it's not possible to detect package's
    # architecture (yes, chroot ... but that doesn't resolve noarch packages).

    def _evr(self):
        # return (epoch, version, release) triplet
        raise NotImplementedError

    @property
    def package_version(self):
        """
        *Version* of the *package* [#footnote_may_be_unknown]_.  Returns `None`
        if epoch is unset.
        """
        _, version, _ = self._evr()
        return version

    @property
    def package_release(self):
        """
        *Release* of the *package* [#footnote_may_be_unknown]_.  Returns `None`
        if epoch is unset.
        """
        _, _, release = self._evr()
        return release

    @property
    def package_epoch(self):
        """
        *Epoch* of the *package* [#footnote_may_be_unknown]_.  Returns `None` if
        epoch is unset.
        """
        epoch, _, _ = self._evr()
        return epoch

    @property
    def package_full_name(self):
        """
        Full - human readable - package name (not meant to be parsed).
        [#footnote_may_be_unknown]_.
        """
        if not self.package_name:
            return None

        (epoch, version, release) = self._evr()

        return "{name}-{epoch}{version}-{release}".format(
            name=self.package_name,
            epoch=epoch + ":" if epoch else "",
            version=version,
            release=release,
        )


class _BuildChrootMessage(_BuildMessage):
    @property
    def chroot(self):
        """
        Build chroot name this build is done in.  For example
        ``fedora-rawhide-x86_64`` or ``epel-7-x86_64``.

        When this is source build, the returned value is ``srpm-builds``.  Each
        build (see :py:attr:`.build_id`) in copr needs to prepare sources first
        (those are imported into copr dist-git) for the following binary-RPM
        builds; so such source build might represent some SCM method execution,
        or e.g. just act of downloading SRPM from a remote URL.
        """
        raise NotImplementedError
