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

import stomp
import json

from .schema import (
        BuildChrootStartedV1,
        BuildChrootEndedV1,
        BuildChrootStartedV1DontUse,
        BuildChrootStartedV1Stomp,
        BuildChrootEndedV1Stomp,
        BuildChrootStartedV1StompDontUse,
)

from .private.consumer import _GenericConsumer


def message_object_from_raw(headers, body):
    destination = headers.get('destination')
    topic = headers.get('topic')
    body = json.loads(body)

    if destination.endswith('.copr.build.end'):
        return BuildChrootEndedV1(body=body)
    if destination.endswith('.copr.build.start'):
        return BuildChrootStartedV1(body=body)
    if destination.endswith('.copr.chroot.start'):
        return BuildChrootStartedV1DontUse(body=body)

    if topic == 'build.start':
        return BuildChrootStartedV1Stomp(body=body)
    if topic == 'build.end':
        return BuildChrootEndedV1Stomp(body=body)
    if topic == 'chroot.start':
        return BuildChrootStartedV1StompDontUse(body=body)


class Consumer(stomp.listener.ConnectionListener, _GenericConsumer):

    def on_message(self, headers, body):
        message = message_object_from_raw(headers, body)
        message.validate()

        if isinstance(message, BuildChrootStartedV1StompDontUse):
            return

        try:
            if isinstance(message, BuildChrootStartedV1) or \
               isinstance(message, BuildChrootStartedV1Stomp):
                self.build_chroot_started(message)
                return

            if isinstance(message, BuildChrootEndedV1) or \
               isinstance(message, BuildChrootEndedV1Stomp):
                self.build_chroot_ended(message)
                return

        except NotImplementedError:
            return
