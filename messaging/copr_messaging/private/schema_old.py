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


from copr_common.enums import StatusEnum
from .hierarchy import _BuildChrootMessage

class _PreFMBuildMessage(_BuildChrootMessage):
    """ old obsoleted msg format """

    """
    This is 'copr.build.end' message schema.

    This message is from the pre-fedora-messaging era.
    """
    body_schema = {
        "id": "http://fedoraproject.org/message-schema/copr#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description":
            "Message sent by Copr build system",
        "type": "object",
        "required": [
            "status",
            "chroot",
            "build",
            "owner",
            "copr",
            "pkg",
            "version",
            "what",
            "ip",
            "who",
            "user",
            "pid",
        ],
        "properties": {
            "status": {
                "type": "number",
                "description": "numerical representation of build status",
            },
            "chroot": {
                "type": "string",
                "description": "what chroot was this build run against, "
                               "'srpm-builds' for source builds",
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
            "build": {
                "type": "number",
                "description": "build id",
            },
            "pkg": {
                "type": ['string', 'null'],
                "description": "Package name, null if unknown",
            },
            "version": {
                "type": ['string', 'null'],
                "description": "Package version, null if unknown",
            },
            "user": {
                "type": ['string', 'null'],
                "description": "Copr user who submitted the build, null if unknown",
            },
            "what": {
                "type": "string",
                "description": "combination of all the fields",
            },
            "ip": {
                "type": ["string", "null"],
                "description": "IP address (usually not public) of the builder",
            },
            "who": {
                "type": ['string'],
                "description": "what python module has sent this message",
            },
            "pid": {
                "type": 'number',
                "description": "process ID of the process on backend taking "
                               "care of the task",
            },
        },
    }

    @property
    def build_id(self):
        return self.body['build']

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
        return StatusEnum(self.body['status'])

    @property
    def package_name(self):
        return self.body.get('pkg')

    def _evr(self):
        evr = self.body.get('version')
        if not evr:
            return (None, None, None)

        e_v = evr .split(':', 1)
        epoch = None
        if len(e_v) == 1:
            v_r = e_v[0]
        else:
            epoch = e_v[0]
            v_r = e_v[1]

        version, release = v_r.split('-', 1)
        return (epoch, version, release)
