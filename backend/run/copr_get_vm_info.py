#!/usr/bin/python3

# coding: utf-8

from copr_backend.helpers import BackendConfigReader
from copr_backend.vm_manage.manager import VmManager


def main():
    opts = BackendConfigReader().read()
    vmm = VmManager(opts, None)
    print(vmm.info())


if __name__ == "__main__":
    main()
