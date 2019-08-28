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

    KRB5_LOGIN_BASEURI = "/krb5_login/"
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
    LOGGING_LEVEL = logging.DEBUG

    SEND_LEGAL_TO = ["root@localhost"]
    REPLY_TO = "copr-devel@lists.fedorahosted.org"

    # post-process url leading to backend
    # possible options: None, "http", "https"
    ENFORCE_PROTOCOL_FOR_BACKEND_URL = None
    # post-process url leading to frontend
    ENFORCE_PROTOCOL_FOR_FRONTEND_URL = None

    PUBLIC_COPR_BASE_URL = "https://copr-fe-dev.cloud.fedoraproject.org"
    PUBLIC_COPR_HOSTNAME = "copr-fe-dev.cloud.fedoraproject.org"

    DIST_GIT_URL = None
    COPR_DIST_GIT_LOGS_URL = None
    MBS_URL = "http://copr-fe-dev.cloud.fedoraproject.org/module/1/module-builds/"

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
        'user_link': 'https://admin.fedoraproject.org/accounts/user/view/{username}/',
        'user_desc': 'fas'
    }

    # Optional, news box shows only when both variables are configured
    NEWS_URL = "https://fedora-copr.github.io/"
    NEWS_FEED_URL = "https://fedora-copr.github.io/feed.xml"

    # When the data in EOL chroots should be deleted (in days)
    DELETE_EOL_CHROOTS_AFTER = 180

    # We may have a (temporary) chroot that doesn't correspond with /etc/os-release
    # on a client system, e.g. "rhelbeta-8" chroots in Copr which doesn't match to
    # any real system, instead it is a temporary alias for "epel-8". In such case,
    # set this to {"epel-8": "rhelbeta-8"}
    CHROOT_NAME_RELEASE_ALIAS = {}

    # How many pinned projects a user or group can have
    PINNED_PROJECTS_LIMIT = 4

    ENABLE_DISCUSSION = False
    DISCOURSE_URL = ''

    WHITELIST_EMAILS = []

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
