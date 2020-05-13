" test vm_alloc.py "

from unittest import mock

from copr_backend.vm_alloc import ResallocHostFactory

@mock.patch('copr_backend.vm_alloc.ResallocConnection')
def test_ticket(_rcon):
    hf = ResallocHostFactory()
    host = hf.get_host()
    host.ticket.collect.return_value = False
    host.check_ready()
    assert host.hostname is None

    host.ticket.collect.return_value = True
    host.ticket.output = "1.1.1.1"
    host.check_ready()
    assert host.hostname == "1.1.1.1"
    host.release()

@mock.patch('copr_backend.vm_alloc.ResallocConnection')
def test_ticket_with_args(rcon):
    hf = ResallocHostFactory()
    host = hf.get_host(sandbox='somesb', tags=['arch_x86_64'])
    host.ticket.collect.return_value = True
    host.ticket.output = "1.1.1.1"
    host.wait_ready()
    assert rcon.return_value.newTicket.call_args_list == [
        mock.call(['copr_builder', 'arch_x86_64'], 'somesb'),
    ]
    assert host.hostname == "1.1.1.1"

@mock.patch('copr_backend.vm_alloc.time.sleep')
@mock.patch('copr_backend.vm_alloc.ResallocConnection')
def test_ticket_wait_ready_normal(_rcon, sleep):
    hf = ResallocHostFactory()
    host = hf.get_host()
    host.ticket.collect.side_effect = [
        False, False, False, False, True,
    ]
    expected_calls = [
        mock.call(3),
        mock.call(3),
        mock.call(6),
        mock.call(6),
    ]
    host.wait_ready()
    assert sleep.call_args_list == expected_calls
    # cached
    host.wait_ready()
    assert sleep.call_args_list == expected_calls

@mock.patch('copr_backend.vm_alloc.time.sleep')
@mock.patch('copr_backend.vm_alloc.ResallocConnection')
def test_ticket_wait_ready_fallback(_rcon, sleep):
    hf = ResallocHostFactory()
    host = hf.get_host()
    host.ticket.collect.side_effect = [False for _ in range(20)] + [True]
    host.wait_ready()
    assert len(sleep.call_args_list) == 20
