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

from fedora_messaging.message import Message

from .private.consumer import _GenericConsumer
from .schema import (
        BuildChrootEnded,
        BuildChrootEndedV1,
        BuildChrootStarted,
        BuildChrootStartedV1,
        BuildChrootStartedV1DontUse,
)


def retype_message(message):
    if type(message) == Message:
        # This message might be actually originated from fedmsg, and the
        # fedmsg->AMQP proxy made things wrong and the fedora-messaging
        # tooling is unable to correctly instanitate it.
        if message.topic.endswith('.copr.build.end'):
            return BuildChrootEndedV1(body=message.body)
        if message.topic.endswith('.copr.build.start'):
            return BuildChrootStartedV1(body=message.body)
        if message.topic.endswith('.copr.chroot.start'):
            return BuildChrootStartedV1DontUse(body=message.body)

    return message


class Consumer(_GenericConsumer):
    """
    Helper.
    """
    def __call__(self, message):
        message = retype_message(message)

        message.validate()

        if isinstance(message, BuildChrootStartedV1DontUse):
            return

        try:
            if isinstance(message, BuildChrootStarted):
                self.build_chroot_started(message)
                return

            if isinstance(message, BuildChrootEnded):
                self.build_chroot_ended(message)
                return
        except NotImplementedError:
            pass


class Printer(Consumer):
    def build_chroot_started(self, message):
        print("build_chroot_started(): {}".format(message))

    def build_chroot_ended(self, message):
        print("build_chroot_ended(): {}".format(message))
