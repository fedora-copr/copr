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
TODO
"""

import copy

from copr_common.enums import StatusEnum

from .hierarchy import _BuildChrootMessage


BODY_SCHEMA = {
    "id": "http://fedoraproject.org/message-schema/copr#",
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "required": [
        "build",
        "owner",
        "copr",
        "submitter",
        "package",
        "chroot",
        "builder",
        "status",
        "status_int",
    ],
    "properties": {
        "build": {
            "type": "string",
            "description": "build id as string",
        },
        "owner": {
            "type": "string",
            "description":
                "owner (grup/user) of the project this build was done in",
        },
        "copr": {
            "type": "string",
            "description": "name of the project the build was built in",
        },
        "submitter": {
            "type": ["string", "null"],
            "description": "who (copr user) submitted this build",
        },
        "package": {
            "type": ['string', 'null'],
            "description": "Package NVR, null if unknown",
        },
        "chroot": {
            "type": "string",
            "description": "what chroot was this build run against, "
                           "'srpm-builds' for source builds",
        },
        "builder": {
            "type": ["string", "null"],
            "description": "IP address (usually not public) of the builder",
        },
        "status": {
            "type": "string",
            "description": "text representation of build status",
        },
        "status_int": {
            "type": "string",
            "description": "integer representation of build status",
        },
    },
}


class _OldStompChrootMessage(_BuildChrootMessage):
    body_schema = copy.deepcopy(BODY_SCHEMA)
    body_schema.update({
        'description': 'hey!',
    })

    @property
    def build_id(self):
        return int(self.body['build'])

    @property
    def project_name(self):
        return str(self.body['copr'])

    @property
    def project_owner(self):
        return str(self.body['owner'])

    @property
    def chroot(self):
        return self.body['chroot']

    @property
    def status(self):
        """
        String representation of build chroot status.
        """
        return StatusEnum(int(self.body['status_int']))

    def _nevr(self):
        nevr = self.body.get('package')
        if nevr == 'None-None':
            # compat hack, for mistakenly sent strings like this before
            return (None, None, None, None)

        nev, release = nevr.rsplit('-', 1)
        name, e_v = nev.rsplit('-', 1)
        e_v_list = e_v.split(':')
        if len(e_v_list) == 1:
            epoch = None
            version = e_v_list[0]
        else:
            epoch = e_v_list[0]
            version = e_v_list[1]

        return (name, epoch, version, release)

    def _evr(self):
        _, epoch, version, release = self._nevr()
        return (epoch, version, release)

    @property
    def package_name(self):
        name, _, _, _ = self._nevr()
        return name
