import os
import rpm


def get_rpm_header(path):
    """
    Get RPM package file and return its header.
    """
    ts = rpm.TransactionSet()
    # I don't want to copy-paste the value of the protected variable.
    # IMHO there is only a low chance it will get removed and even if it gets,
    # we have tests to catch it anyway
    # pylint: disable=protected-access
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
    with open(path, "rb") as f:
        hdr = ts.hdrFromFdno(f.fileno())
        return hdr


def get_rpm_nevra_dict(path):
    """
    Take a package path and return its NEVRA as a `dict` with
    name/epoch/version/release/arch keys.
    """
    filename = os.path.basename(path)
    if not filename.endswith(".rpm"):
        raise ValueError(f"File name doesn't end with '.rpm': {path}")

    hdr = get_rpm_header(path)
    if not hdr:
        raise ValueError("Could not read RPM header from: {}".format(path))
    arch = "src" if filename.endswith(".src.rpm") else hdr["arch"]
    return {
        "name": hdr["name"],
        "epoch": hdr["epoch"],
        "version": hdr["version"],
        "release": hdr["release"],
        "arch": arch,
    }


# TODO: is there something like python-rpm-utils or python-dnf-utils for this?
def splitFilename(filename):
    """
    Pass in a standard style rpm fullname

    Return a name, version, release, epoch, arch, e.g.::
        foo-1.0-1.i386.rpm returns foo, 1.0, 1, i386
        1:bar-9-123a.ia64.rpm returns bar, 9, 123a, 1, ia64
    """

    if filename[-4:] == '.rpm':
        filename = filename[:-4]

    archIndex = filename.rfind('.')
    arch = filename[archIndex+1:]

    relIndex = filename[:archIndex].rfind('-')
    rel = filename[relIndex+1:archIndex]

    verIndex = filename[:relIndex].rfind('-')
    ver = filename[verIndex+1:relIndex]

    epochIndex = filename.find(':')
    if epochIndex == -1:
        epoch = ''
    else:
        epoch = filename[:epochIndex]

    name = filename[epochIndex + 1:verIndex]
    return name, ver, rel, epoch, arch
