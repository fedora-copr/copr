# coding: utf-8

"""
Unit tests for the Kafka message bus support in copr_backend.msgbus.
"""

# pylint: disable=redefined-outer-name,protected-access

from unittest import mock
from munch import Munch
import pytest

from copr_backend.msgbus import MsgBusKafka, MessageSender, message_from_worker_job


@pytest.fixture
def kafka_producer():
    "patch copr_backend.msgbus.KafkaProducer, and return the mocked class"
    with mock.patch("copr_backend.msgbus.KafkaProducer") as obj:
        yield obj


@pytest.fixture
def bus_opts():
    return Munch(
        bus_type='kafka',
        hosts=['broker1:9096'],
        auth={'username': 'copr-backend', 'password': 'secret'},
        destination='dev.copr.build-events',
    )


class TestMsgBusKafka:
    def test_send_message(self, kafka_producer, bus_opts):
        bus = MsgBusKafka(bus_opts)
        # a MagicMock (not Munch) so message.validate() is a harmless no-op,
        # like a real fedora_messaging.message.Message would be
        message = mock.MagicMock(topic='build.start', body={'build': '123'})

        bus.send_message(message)

        producer = kafka_producer.return_value
        producer.send.assert_called_once_with(
            'dev.copr.build-events',
            value={'build': '123'},
            headers=[('topic', b'build.start')],
        )
        producer.send.return_value.get.assert_called_once_with(timeout=10)

    def test_send_message_failure_propagates(self, kafka_producer, bus_opts):
        bus = MsgBusKafka(bus_opts)
        producer = kafka_producer.return_value
        producer.send.return_value.get.side_effect = Exception("boom")

        message = mock.MagicMock(topic='build.end', body={'build': '123'})
        # _send_message() itself must let the failure raise, so that
        # MsgBus.send_message()'s (untouched, existing) retry loop can catch
        # and retry it -- that retry loop is not re-tested here
        with pytest.raises(Exception, match="boom"):
            bus._send_message(message)


def test_message_sender_dispatches_kafka_bus(kafka_producer, bus_opts):
    backend_opts = Munch(msg_buses=[bus_opts], fedmsg_enabled=False)
    sender = MessageSender(backend_opts, name='test', log=mock.MagicMock())

    assert len(sender.msg_buses) == 1
    assert isinstance(sender.msg_buses[0], MsgBusKafka)
    # also confirms MessageSender actually constructed a real KafkaProducer,
    # not just an MsgBusKafka wrapper around nothing
    kafka_producer.assert_called_once()


@pytest.mark.parametrize("style", ["v1", "v1stomp"])
@pytest.mark.parametrize("topic", ["build.start", "chroot.start", "build.end"])
@pytest.mark.parametrize("href", [None, "/pulp/api/v3/publications/rpm/rpm/snapshot/"])
def test_optional_snapshot_message(style, topic, href):
    """Emit nested metadata only for completed builds with a known snapshot."""
    job = Munch(
        submitter="owner", project_name="project", project_owner="owner",
        package_name="pkg", build_id=123, chroot="fedora-rawhide-x86_64",
        package_version="1-1", status=1, pulp_publication_href=href,
    )
    with mock.patch("copr_backend.msgbus.schema") as schema:
        message_from_worker_job(style, topic, job, "worker", "127.0.0.1", 1)
    body = schema.mock_calls[0].kwargs["body"]
    assert "pulp_publication_href" not in body
    if topic == "build.end" and href:
        assert body["pulp"] == {"publication_href": href}
    else:
        assert "pulp" not in body
