import os
import logging


class Config(object):
    DATA_DIR = os.path.join(os.path.dirname(__file__), "../../data")
    DATABASE = os.path.join(DATA_DIR, "copr.db")
    OPENID_STORE = os.path.join(DATA_DIR, "openid_store")
    WHOOSHEE_DIR = os.path.join(DATA_DIR, "whooshee")
    SECRET_KEY = "THISISNOTASECRETATALL"
    BACKEND_PASSWORD = "thisisbackend"

    KRB5_LOGIN_BASEURI = "/krb5_login/"
    KRB5_LOGIN = {}

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
    LOGGING_LEVEL = logging.ERROR

    SEND_LEGAL_TO = ["root@localhost"]

    # prefer http or https, default setting preserve old behaviour
    USE_HTTPS_FOR_RESULTS = True

    ENFORCE_PROTOCOL_FOR_BACKEND_URL = "https"
    ENFORCE_PROTOCOL_FOR_FRONTEND_URL = "https"


class ProductionConfig(Config):
    DEBUG = False
    #SECRET_KEY = "put_some_secret_here"
    #BACKEND_PASSWORD = "password_here"
    #SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://login:password@/db_name"


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

    ENFORCE_PROTOCOL_FOR_BACKEND_URL = "http"
    ENFORCE_PROTOCOL_FOR_FRONTEND_URL = "http"



class UnitTestConfig(Config):
    CSRF_ENABLED = False
    DATABASE = os.path.abspath("tests/data/copr.db")
    OPENID_STORE = os.path.abspath("tests/data/openid_store")
    WHOOSHEE_DIR = os.path.abspath("tests/data/whooshee")

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.abspath(DATABASE)
