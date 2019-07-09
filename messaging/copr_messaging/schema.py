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
This file contains schemas for messages sent by Copr project.
"""

import copy

from copr_common.enums import StatusEnum
from fedora_messaging import message

from .private.hierarchy import _BuildChrootMessage
from .private.schema_old import _PreFMBuildMessage
from .private import schema_stomp_old


class BuildChrootEnded(_BuildChrootMessage):
    """
    Representation of a message sent by Copr build system right after some Copr
    worker finished a build in a particular mock chroot.
    """
    @property
    def status(self):
        """
        string representation of build status, e.g. ``succeeded``, ``failed``
        """
        raise NotImplementedError

    def __str__(self):
        return '{0}: chroot "{1}" ended as "{2}".'.format(
            super(BuildChrootEnded, self)._str_prefix(),
            self.chroot,
            self.status,
        )


class BuildChrootStarted(_BuildChrootMessage):
    """
    Representation of a message sent by Copr build system right before some Copr
    worker starts working on a build in a particular mock chroot.
    """
    def __str__(self):
        return '{0}: chroot "{1}" started.'.format(
            super(BuildChrootStarted, self)._str_prefix(),
            self.chroot,
        )


class BuildChrootStartedV1(_PreFMBuildMessage, BuildChrootStarted):
    """
    schema for the old fedmsg-era 'copr.build.start' message
    """
    topic = 'copr.build.start'


class BuildChrootEndedV1(_PreFMBuildMessage, BuildChrootEnded):
    """
    schema for the old fedmsg-era 'copr.build.end' message
    """
    topic = 'copr.build.end'

    @property
    def status(self):
        return StatusEnum(self.body['status'])


class BuildChrootStartedV1DontUse(_PreFMBuildMessage, BuildChrootStarted):
    """
    Schema for the old fedmsg-era 'copr.chroot.start' message, this message
    duplicated the 'copr.build.start' message, so you should never use this.
    """
    topic = 'copr.chroot.start'


class BuildChrootStartedV1Stomp(schema_stomp_old._OldStompChrootMessage,
                                BuildChrootStarted):
    topic = 'build.start'
    body_schema = copy.deepcopy(schema_stomp_old.BODY_SCHEMA)
    body_schema.update({
        'description': ""
    })


class BuildChrootStartedV1StompDontUse(message.Message):
    topic = 'chroot.start'

    body_schema = {
        "id": "http://fedoraproject.org/message-schema/copr#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description":
            "Message sent by Copr build system when build in "
            "concrete chroot started",
        "type": "object",
        "required": [
            "chroot",
        ],
        "properties": {
            "chroot": {
                "type": "string",
                "description": "what chroot was this build run against, "
                               "'srpm-builds' for source builds",
            },
        },
    }


class BuildChrootEndedV1Stomp(schema_stomp_old._OldStompChrootMessage,
                              BuildChrootEnded):
    topic = 'build.end'

    body_schema = copy.deepcopy(schema_stomp_old.BODY_SCHEMA)
    body_schema.update({
        'description': ""
    })

    @property
    def status(self):
        return StatusEnum(int(self.body['status_int']))
