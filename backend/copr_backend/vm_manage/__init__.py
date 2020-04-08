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


KEY_VM_POOL = "copr:backend:vm_pool:set::{group}"
# set of vm_names of vm available for `group`

KEY_VM_POOL_INFO = "copr:backend:vm_pool_info:hset::{group}"
# hset with additional information for `group`, used fields:
# - "last_vm_spawn_start": latest time when VM spawn was initiated for this `group`

KEY_SERVER_INFO = "copr:backend:server_info:hset::"
# common shared info about server, not stritly related to VMM, maybe move it to helpers later
# used fields:
#   "server_start_timestamp" -> unixtime string

KEY_VM_INSTANCE = "copr:backend:vm_instance:hset::{vm_name}"
# hset to store VmDescriptor
