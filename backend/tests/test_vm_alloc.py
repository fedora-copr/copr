" test vm_alloc.py "

from unittest import mock

import pytest

from copr_backend.vm_alloc import (
    RemoteHostAllocationTerminated,
    ResallocHostFactory,
)

@mock.patch('copr_backend.vm_alloc.ResallocConnection')
def test_ticket(_rcon):
    hf = ResallocHostFactory()
    host = hf.get_host()

    host.ticket.closed = False
    host.ticket.ready = False
    assert not host.check_ready()
    assert host.hostname is None

    host.ticket.output = "1.1.1.1"
    host.ticket.ready = True
    assert host.check_ready()
    assert host.hostname == "1.1.1.1"

    host.ticket.closed = True
    with pytest.raises(RemoteHostAllocationTerminated):
        assert host.check_ready()
    host.release()

@mock.patch('copr_backend.vm_alloc.ResallocConnection')
def test_ticket_with_args(rcon):
    hf = ResallocHostFactory()
    host = hf.get_host(sandbox='somesb', tags=['arch_x86_64'])
    host.ticket.closed = False
    host.ticket.ready = True
    host.ticket.output = "1.1.1.1"
    host.wait_ready()
    assert rcon.return_value.newTicket.call_args_list == [
        mock.call(['copr_builder', 'arch_x86_64'], 'somesb'),
    ]
    assert host.hostname == "1.1.1.1"

class _collect_side_effect:
    def __init__(self, results, host):
        self.returns = results
        self.counter = 0
        self.host = host
    def __call__(self):
        ret = self.returns[self.counter]
        self.host.ticket.closed = ret == 'closed'
        self.host.ticket.ready = ret is True
        self.host.ticket.output = "host" if ret else None
        self.counter += 1

@mock.patch('copr_backend.vm_alloc.time.sleep')
@mock.patch('copr_backend.vm_alloc.ResallocConnection')
def test_ticket_wait_ready_normal(_rcon, sleep):
    hf = ResallocHostFactory()
    host = hf.get_host()
    host.ticket.collect.side_effect = _collect_side_effect(
        [False, False, False, False, True],
        host,
    )
    expected_calls = [
        mock.call(3),
        mock.call(3),
        mock.call(6),
        mock.call(6),
    ]
    host.wait_ready()
    assert sleep.call_args_list == expected_calls
    assert host.hostname == "host"
    # cached
    host.wait_ready()
    assert sleep.call_args_list == expected_calls

@mock.patch('copr_backend.vm_alloc.time.sleep')
@mock.patch('copr_backend.vm_alloc.ResallocConnection')
def test_ticket_wait_ready_raises(_rcon, sleep):
    hf = ResallocHostFactory()
    host = hf.get_host()
    host.ticket.collect.side_effect = _collect_side_effect(
        [False, 'closed'],
        host,
    )
    expected_calls = [mock.call(3)]
    assert not host.wait_ready()
    assert sleep.call_args_list == expected_calls


@mock.patch('copr_backend.vm_alloc.time.sleep')
@mock.patch('copr_backend.vm_alloc.ResallocConnection')
def test_ticket_wait_ready_fallback(_rcon, sleep):
    hf = ResallocHostFactory()
    host = hf.get_host()

    host.ticket.collect.side_effect = _collect_side_effect(
        [False for _ in range(20)] + [True],
        host,
    )
    host.wait_ready()
    assert len(sleep.call_args_list) == 20
