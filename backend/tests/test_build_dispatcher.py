""" test counting priority of build task """

import pytest

from copr_backend.rpm_builds import BuildQueueTask, PRIORITY_SECTION_SIZE
from copr_backend.daemons.build_dispatcher import _PriorityCounter


def test_priority_numbers():
    prio = _PriorityCounter()
    assert prio.get_priority(BuildQueueTask({
        "build_id": "7",
        "task_id": "7",
        "project_owner": "cecil",
    })) == 1
    assert prio.get_priority(BuildQueueTask({
        "build_id": "8",
        "task_id": "8",
        "project_owner": "cecil",
    })) == 2
    assert prio.get_priority(BuildQueueTask({
        "build_id": "88",
        "task_id": "88",
        "project_owner": "cecil",
        "background": True,
    })) == 1  # background jobs have separate counters

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

@pytest.mark.parametrize('background,result',
                         [(True, 2*PRIORITY_SECTION_SIZE), (False, 0)])
def test_frontend_priority(background, result):
    task = BuildQueueTask({
        "build_id": "9",
        "task_id": "9",
        "project_owner": "cecil",
        "background": background,
    })
    assert task.frontend_priority == result
    task = BuildQueueTask({
        "build_id": "9",
        "task_id": "9-fedora-rawhide-x86_64",
        "project_owner": "cecil",
        "background": background,
    })
    assert task.frontend_priority == result + PRIORITY_SECTION_SIZE


def test_sandbox_priority():
    prio = _PriorityCounter()
    assert prio.get_priority(BuildQueueTask({
        "build_id": "9",
        "task_id": "9",
        "project_owner": "cecil",
        "background": False,
        "sandbox": "cecil/foo--submitter",
    })) == 1

    assert prio.get_priority(BuildQueueTask({
        "build_id": "9",
        "task_id": "9-fedora-rawhide-x86_64",
        "chroot": "fedora-rawhide-x86_64",
        "project_owner": "cecil",
        "background": True,
        "sandbox": "cecil/foo--submitter",
    })) == 1  # different arch

    assert prio.get_priority(BuildQueueTask({
        "build_id": "10",
        "task_id": "10-fedora-rawhide-x86_64",
        "chroot": "fedora-rawhide-x86_64",
        "project_owner": "cecil",
        "background": True,
        "sandbox": "cecil/foo--submitter",
    })) == 2  # the same arch

    assert prio.get_priority(BuildQueueTask({
        "build_id": "11",
        "task_id": "11-fedora-rawhide-x86_64",
        "chroot": "fedora-rawhide-x86_64",
        "project_owner": "cecil",
        "background": True,
        "sandbox": "cecil/baz--submitter",
    })) == 1  # the same arch, but different sandbox
