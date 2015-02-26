# coding: utf-8


class VmStates(object):
    GOT_IP = "got_ip"
    CHECK_HEALTH = "check_health"
    CHECK_HEALTH_FAILED = "check_health_failed"
    READY = "ready"
    IN_USE = "in_use"
    TERMINATING = "terminating"

# for IPC
PUBSUB_MB = "copr:backend:vm:pubsub::"


class EventTopics(object):
    HEALTH_CHECK = "health_check"
    VM_SPAWNED = "vm_spawned"
    VM_TERMINATION_REQUEST = "vm_termination_request"
    VM_TERMINATED = "vm_terminated"

# argument - vm_ip
PUBSUB_INTERRUPT_BUILDER = "copr:backend:interrupt_build:pubsub::{}"

PUBSUB_VM_TERMINATION = "copr:backend:vm_termination:pubsub::{vm_name}"
# message should contain string "terminating"

KEY_VM_GROUPS = "copr:backend:vm_groups:set::"
# set of available groups,
# TODO: remove it, use opts.build_groups_count

KEY_VM_POOL = "copr:backend:vm_pool:set::{group}"
# set of vm_names of vm available for `group`

KEY_VM_POOL_INFO = "copr:backend:vm_pool_info:hset::{group}"
# hashset with additional information for `group`, used fields:
# - "last_vm_spawn_start": latest time when VM spawn was initiated for this `group`

KEY_VM_INSTANCE = "copr:backend:vm_instance:hset::{vm_name}"
# hset to store VmDescriptor


class Thresholds(object):
    """
    Time constants for VM manager, all values are int and represents seconds
    """
    health_check_max_time = 120
    terminating_timeout = 600
    dirty_vm_terminating_timeout = 120  # how long we keep released vms
    health_check_period = 60
    vm_spawn_min_interval = 20
    cycle_timeout = 5
    max_check_fails = 2
