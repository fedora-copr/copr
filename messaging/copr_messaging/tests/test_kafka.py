# pylint: skip-file

"""Unit tests for the Kafka consumer helper."""

import json
import unittest
from collections import namedtuple

from .. import kafka
from .. import schema

_Record = namedtuple('_Record', ['value', 'headers'])

VALID_V1_BODY = {
    "status": 3,
    "what": "build start: user:praiskup copr:ping pkg:None build:38492 "
            "ip:10.8.29.188 pid:1",
    "chroot": "srpm-builds",
    "ip": "10.8.29.188",
    "user": "praiskup",
    "who": "backend.worker",
    "pid": 1,
    "copr": "ping",
    "version": None,
    "build": 38492,
    "owner": "praiskup",
    "pkg": None,
}


def _record(topic, body):
    return _Record(
        value=json.dumps(body).encode('utf-8'),
        headers=[('topic', topic.encode('utf-8'))],
    )


class _FakeKafkaConsumer:
    def __init__(self, records):
        self._records = records
        self.commit_count = 0

    def __iter__(self):
        return iter(self._records)

    def commit(self):
        self.commit_count += 1


class _TrackingConsumer(kafka.Consumer):
    def __init__(self):
        self.started = []
        self.ended = []

    def build_chroot_started(self, message):
        self.started.append(message)

    def build_chroot_ended(self, message):
        self.ended.append(message)


class MessageObjectFromRawTest(unittest.TestCase):
    def test_dispatch(self):
        cases = [
            ('copr.build.start', VALID_V1_BODY, schema.BuildChrootStartedV1),
            ('copr.build.end', VALID_V1_BODY, schema.BuildChrootEndedV1),
            ('copr.chroot.start', VALID_V1_BODY,
             schema.BuildChrootStartedV1DontUse),
            ('some.unknown.topic', {}, type(None)),
        ]
        for topic, body, expected_class in cases:
            raw_value = json.dumps(body).encode('utf-8')
            message = kafka.message_object_from_raw({'topic': topic}, raw_value)
            self.assertIsInstance(message, expected_class)


class ConsumerTest(unittest.TestCase):
    def test_consume_forever_dispatches_and_commits(self):
        records = [
            _record('copr.build.start', VALID_V1_BODY),
            _record('copr.build.end', VALID_V1_BODY),
        ]
        consumer = _TrackingConsumer()
        fake_kafka_consumer = _FakeKafkaConsumer(records)

        consumer.consume_forever(fake_kafka_consumer)

        self.assertEqual(len(consumer.started), 1)
        self.assertEqual(len(consumer.ended), 1)
        self.assertEqual(fake_kafka_consumer.commit_count, 2)

    def test_consume_forever_skips_callbacks_for_dontuse_and_unknown(self):
        records = [
            _record('copr.chroot.start', VALID_V1_BODY),
            _record('some.unknown.topic', {}),
        ]
        consumer = _TrackingConsumer()
        fake_kafka_consumer = _FakeKafkaConsumer(records)

        consumer.consume_forever(fake_kafka_consumer)

        self.assertEqual(consumer.started, [])
        self.assertEqual(consumer.ended, [])
        # still commits both, so a message we don't care about doesn't get
        # redelivered forever
        self.assertEqual(fake_kafka_consumer.commit_count, 2)
