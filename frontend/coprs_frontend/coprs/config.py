import os
import logging


class Config(object):
    ENV = "devel"
    DATA_DIR = os.path.join(os.path.dirname(__file__), "../../data")
    DATABASE = os.path.join(DATA_DIR, "copr.db")
    OPENID_STORE = os.path.join(DATA_DIR, "openid_store")
    WHOOSHEE_DIR = os.path.join(DATA_DIR, "whooshee")
    SECRET_KEY = "THISISNOTASECRETATALL"
    BACKEND_PASSWORD = "thisisbackend"
    BACKEND_BASE_URL = "http://copr-be-dev.cloud.fedoraproject.org"
    BACKEND_STATS_URI = None

    KRB5_LOGIN = {}

    OPENID_PROVIDER_URL = "https://id.fedoraproject.org"

    # restrict access to a set of users
    USE_ALLOWED_USERS = False
    ALLOWED_USERS = []

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.abspath(DATABASE)

    # Token length, defaults to 30, DB set to varchar 255
    API_TOKEN_LENGTH = 30

    # Expiration of API token in days
    API_TOKEN_EXPIRATION = 180

    # logging options
    SEND_LOGS_TO = ["root@localhost"]
    LOGGING_LEVEL = 'info'

    SEND_LEGAL_TO = ["root@localhost"]
    REPLY_TO = "copr-devel@lists.fedorahosted.org"

    # post-process url leading to backend
    # possible options: None, "http", "https"
    ENFORCE_PROTOCOL_FOR_BACKEND_URL = None
    # post-process url leading to frontend
    ENFORCE_PROTOCOL_FOR_FRONTEND_URL = None

    PUBLIC_COPR_BASE_URL = "https://copr.stg.fedoraproject.org"
    PUBLIC_COPR_HOSTNAME = "copr.stg.fedoraproject.org"

    DIST_GIT_URL = None
    COPR_DIST_GIT_LOGS_URL = None
    MBS_URL = "http://copr.stg.fedoraproject.org/module/1/module-builds/"

    # primary log file
    LOG_FILENAME = "/var/log/copr-frontend/frontend.log"
    LOG_DIR = "/var/log/copr-frontend/"

    INTRANET_IPS = ["127.0.0.1"]
    DEBUG = True

    REPO_GPGCHECK = 1

    # should baseurls in '.repo' files always use http:// links?
    REPO_NO_SSL = False

    STORAGE_DIR = "/var/lib/copr/data/srpm_storage/"

    LAYOUT_OVERVIEW_HIDE_QUICK_ENABLE = False

    # We enable authentication against FAS by default.
    FAS_LOGIN = True

    LOGIN_INFO = {
        'user_link': 'https://accounts.fedoraproject.org/user/{username}/',
        'user_desc': 'fas'
    }

    # Optional, news box shows only when both variables are configured
    NEWS_URL = "https://fedora-copr.github.io/"
    NEWS_FEED_URL = "https://fedora-copr.github.io/feed.xml"

    # When the data in EOL chroots should be deleted (in days)
    DELETE_EOL_CHROOTS_AFTER = 180

    # Days between notification emails about a chroot
    EOL_CHROOTS_NOTIFICATION_PERIOD = 80

    # When clicking to the "expire" button, how long it should take before we
    # actually delete the data. When setting this option to 0, then the data is
    # immediatelly ready to be removed, and it will be done on next cron-triggered
    # cleanup. It is probably better to expire the chroot and leave e.g. 12 hours
    # remaining, in case the user changes his mind.
    EOL_CHROOTS_EXPIRE_PERIOD = 0.5

    # We may have a (temporary) chroot that doesn't correspond with /etc/os-release
    # on a client system, e.g. "rhelbeta-8" chroots in Copr which doesn't match to
    # any real system, instead it is a temporary alias for "epel-8". In such case,
    # set this to {"epel-8": "rhelbeta-8"}
    CHROOT_NAME_RELEASE_ALIAS = {}

    # How many pinned projects a user or group can have
    PINNED_PROJECTS_LIMIT = 4

    ENABLE_DISCUSSION = False
    DISCOURSE_URL = ''

    ALLOWLIST_EMAILS = []

    # PAGINATION
    ITEMS_PER_PAGE = 10
    PAGES_URLS_COUNT = 5

    # Builds defaults
    # # memory in MB
    DEFAULT_BUILD_MEMORY = 2048
    MIN_BUILD_MEMORY = 2048
    MAX_BUILD_MEMORY = 4096
    # in seconds
    DEFAULT_BUILD_TIMEOUT = 3600 * 5
    MIN_BUILD_TIMEOUT = 0
    MAX_BUILD_TIMEOUT = 108000
    MEMORY_ANALYZER = False

    API_GSSAPI_AUTH = True

    ##### DEVEL Section ####
    # Enable flask-profiler
    # Setting this to True requires special installation
    PROFILER = False

    # We remove pull-request directories after some time.
    KEEP_PR_DIRS_DAYS = 40

    # Caching templates
    # https://flask-caching.readthedocs.io/en/latest/
    # To enable caching set `CACHE_TYPE` to "redis". To disable it (e.g. for
    # development purposes), set it to "NullCache"
    CACHE_TYPE = "redis"
    CACHE_REDIS_DB = 1  # we use 0 for sessions
    CACHE_KEY_PREFIX = "copr_cache_"

    # Default value for temporary projects
    DELETE_AFTER_DAYS = 60

    # Turn-on the in-code checkpoints (additional logging info output).  See the
    # 'measure.py' module for more info.
    DEBUG_CHECKPOINTS = False

    FAS_SIGNUP_URL = "https://accounts.fedoraproject.org/"

    HIDE_IMPORT_LOG_AFTER_DAYS = 14

    # LDAP server URL, e.g. ldap://ldap.foo.company.com
    LDAP_URL = None

    # e.g. ou=users,dc=company,dc=com
    LDAP_SEARCH_STRING = None


class ProductionConfig(Config):
    DEBUG = False
    # SECRET_KEY = "put_some_secret_here"
    # BACKEND_PASSWORD = "password_here"
    # SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://login:password@/db_name"
    PUBLIC_COPR_HOSTNAME = "copr.fedoraproject.org"


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

    ENFORCE_PROTOCOL_FOR_BACKEND_URL = "http"
    ENFORCE_PROTOCOL_FOR_FRONTEND_URL = "http"

    PUBLIC_COPR_HOSTNAME = "localhost:5000"


class UnitTestConfig(Config):
    CSRF_ENABLED = False
    DATABASE = os.path.abspath("tests/data/copr.db")
    OPENID_STORE = os.path.abspath("tests/data/openid_store")
    WHOOSHEE_DIR = os.path.abspath("tests/data/whooshee")

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.abspath(DATABASE)

    PUBLIC_COPR_HOSTNAME = "localhost:5000"
