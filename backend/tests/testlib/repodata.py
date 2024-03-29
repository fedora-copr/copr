"""
Re-usable methods for testing related to RPM metadata.
"""

import os
import glob
import gzip
from xml.dom import minidom

try:
    # This import tracebacks on F37 but we need it only on F39+
    # pylint: disable=import-outside-toplevel
    from zstandard import ZstdDecompressor
except ImportError:
    pass


def load_primary_xml(dirname):
    '''
    Parse priary.xml from the given repodata directory path, and return
    dictiony with imporatant informations (package locations, names, etc.).
    '''
    packages = {}
    hrefs = set()
    names = set()
    primary = glob.glob(os.path.join(dirname, '*primary*xml*'))[0]
    xml_content = extract(primary)

    dom = minidom.parseString(xml_content)

    for d_package in dom.getElementsByTagName('package'):
        name = d_package.getElementsByTagName('name')[0].firstChild.nodeValue
        checksum = d_package.getElementsByTagName('checksum')[0].getAttribute('type')
        names.add(name)
        packages[name] = {'name': name, 'chksum_type': checksum}
        package = packages[name]
        package['href'] = d_package.getElementsByTagName('location')[0].getAttribute('href')
        package['xml:base'] = d_package.getElementsByTagName('location')[0].getAttribute('xml:base')
        hrefs.add(package['href'])

    return {
        'packages': packages,
        'hrefs': hrefs,
        'names': names,
    }

def extract(path):
    if path.endswith(".zst"):
        with open(path, "rb") as fp:
            decompressor = ZstdDecompressor()
            return decompressor.stream_reader(fp).read()

    if path.endswith(".gz"):
        with gzip.open(path) as fp:
            return fp.read()
    raise ValueError("Unexpected extension: {0}".format(path))
