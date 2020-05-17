""" test counting priority of build task """

import pytest

from copr_backend.rpm_builds import BuildQueueTask
from copr_backend.daemons.build_dispatcher import _PriorityCounter


def test_priority_numbers():
    prio = _PriorityCounter()
    assert prio.get_priority(BuildQueueTask({
        "build_id": "7",
        "task_id": "7",
        "project_owner": "cecil",
    })) == -9
    assert prio.get_priority(BuildQueueTask({
        "build_id": "8",
        "task_id": "8",
        "project_owner": "cecil",
    })) == -8

    assert prio.get_priority(BuildQueueTask({
        "build_id": "9",
        "task_id": "9-fedora-rawhide-x86_64",
        "chroot": "fedora-rawhide-x86_64",
        "project_owner": "cecil",
        "background": True,
    })) == 1
    assert prio.get_priority(BuildQueueTask({
        "build_id": "10",
        "task_id": "10-fedora-rawhide-i386",
        "chroot": "fedora-rawhide-i386",
        "project_owner": "cecil",
        "background": True,
    })) == 2
    assert prio.get_priority(BuildQueueTask({
        "build_id": "10",
        "task_id": "10-fedora-rawhide-aarch64",
        "chroot": "fedora-rawhide-aarch64",
        "project_owner": "cecil",
        "background": True,
    })) == 1
    assert prio.get_priority(BuildQueueTask({
        "build_id": "11",
        "task_id": "11-fedora-rawhide-aarch64",
        "chroot": "fedora-rawhide-aarch64",
        "project_owner": "bedrich",
        "background": True,
    })) == 1

@pytest.mark.parametrize('background,result', [(True, 10), (False, 0)])
def test_frontend_priority(background, result):
    task = BuildQueueTask({
        "build_id": "9",
        "task_id": "9",
        "project_owner": "cecil",
        "background": background,
    })
    assert task.frontend_priority == result
