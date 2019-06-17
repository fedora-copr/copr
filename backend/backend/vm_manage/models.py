# coding: utf-8

from pprint import pformat
from backend.exceptions import VmDescriptorNotFound
from . import KEY_VM_INSTANCE


class VmDescriptor(object):
    def __init__(self, vm_ip, vm_name, group, state):
        self.vm_ip = vm_ip
        self.vm_name = vm_name
        self.state = state
        self.group = int(group)

        self.bound_to_user = None
        self.used_by_worker = None
        self.task_id = None
        self.sandbox = None

    @property
    def vm_key(self):
        return KEY_VM_INSTANCE.format(vm_name=self.vm_name)

    def __str__(self):
        return pformat(self.__dict__)

    def to_dict(self):
        return {str(k): str(v) for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, raw):
        vmd = cls(raw.pop("vm_ip"), raw.pop("vm_name"), raw.pop("group"), raw.pop("state"))
        vmd.__dict__.update(raw)
        return vmd

    @classmethod
    def load(cls, rc, vm_name):
        """

        :param rc:
        :param vm_name:
        :rtype: VmDescriptor
        :raises VmDescriptorNotFound:
        """
        raw = rc.hgetall(KEY_VM_INSTANCE.format(vm_name=vm_name))
        if not raw:
            raise VmDescriptorNotFound("VmDescriptor for `{}` not found".format(vm_name))
        return cls.from_dict(raw)

    def store(self, rc):
        """
        :type rc: StrictRedis
        """
        rc.hmset(KEY_VM_INSTANCE.format(vm_name=self.vm_name), self.__dict__)

    def store_field(self, rc, field, value):
        """
        :type rc: StrictRedis
        """
        # TODO: add option `save_with_existnse_check`, use lua script to ensure that VMD still exists
        setattr(self, field, value)
        rc.hset(KEY_VM_INSTANCE.format(vm_name=self.vm_name), field, value)

    def get_field(self, rc, field):
        """
        :type rc: StrictRedis
        """
        value = rc.hget(KEY_VM_INSTANCE.format(vm_name=self.vm_name), field)
        setattr(self, field, value)
        return value

    # def record_failure(self, rc):
    #     """
    #     :type rc: StrictRedis
    #     """
    #     rc.hincrby(KEY_VM_INSTANCE.format(vm_name=self.vm_name), "check_fails")
