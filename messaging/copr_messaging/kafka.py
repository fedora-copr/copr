"""
Helpers for consuming Copr's build-event messages from Kafka.
"""

import json

from .schema import (
    BuildChrootStartedV1,
    BuildChrootEndedV1,
    BuildChrootStartedV1DontUse,
)
from .private.consumer import _GenericConsumer


def message_object_from_raw(headers, raw_value):
    """
    Turn a raw Kafka record into the matching schema message object.
    """
    body = json.loads(raw_value)
    topic = headers.get('topic')

    if topic == 'copr.build.start':
        return BuildChrootStartedV1(body=body)
    if topic == 'copr.build.end':
        return BuildChrootEndedV1(body=body)
    if topic == 'copr.chroot.start':
        return BuildChrootStartedV1DontUse(body=body)
    return None


class Consumer(_GenericConsumer):
    """
    Helper for consuming Copr's Kafka messages.
    """

    # pylint: disable=abstract-method
    def consume_forever(self, kafka_consumer):
        """
        Iterate over `kafka_consumer` forever, dispatching each build event
        to build_chroot_started()/build_chroot_ended() and committing every
        record (including ones we don't care about) so it isn't redelivered.
        """
        for record in kafka_consumer:
            headers = dict(
                (k, v.decode('utf-8')) for k, v in (record.headers or [])
            )
            message = message_object_from_raw(headers, record.value)
            if message is None:
                kafka_consumer.commit()
                continue

            message.validate()
            if not isinstance(message, BuildChrootStartedV1DontUse):
                try:
                    if isinstance(message, BuildChrootStartedV1):
                        self.build_chroot_started(message)
                    elif isinstance(message, BuildChrootEndedV1):
                        self.build_chroot_ended(message)
                except NotImplementedError:
                    pass

            kafka_consumer.commit()
