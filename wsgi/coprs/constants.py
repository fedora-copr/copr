# Settings for chroots
INTEL_ARCHES = ['i386', 'x86_64']
DEFAULT_ARCHES = INTEL_ARCHES

CHROOTS = {'fedora-16':      DEFAULT_ARCHES,
           'fedora-17':      DEFAULT_ARCHES,
           'fedora-18':      DEFAULT_ARCHES,
           'fedora-rawhide': DEFAULT_ARCHES,
          }

# PAGINATION
ITEMS_PER_PAGE = 10
PAGES_URLS_COUNT = 5

# Builds defaults
## memory in MB
DEFAULT_BUILD_MEMORY = 2048
MIN_BUILD_MEMORY = 2048
MAX_BUILD_MEMORY = 4096
## in seconds
DEFAULT_BUILD_TIMEOUT = 1800
MIN_BUILD_TIMEOUT = 180
MAX_BUILD_TIMEOUT = 36000
