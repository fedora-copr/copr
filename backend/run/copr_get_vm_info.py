# coding: utf-8


from backend.helpers import BackendConfigReader
from backend.vm_manage.manager import VmManager


def main():
    opts = BackendConfigReader().read()
    vmm = VmManager(opts, None)
    vmm.post_init()
    print(vmm.info())


if __name__ == "__main__":
    main()
