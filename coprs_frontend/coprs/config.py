import os

class Config(object):
    DATA_DIR = os.path.join(os.path.dirname(__file__), '../../data')
    DATABASE = os.path.join(DATA_DIR, 'copr.db')
    OPENID_STORE = os.path.join(DATA_DIR, 'openid_store')
    SECRET_KEY = 'THISISNOTASECRETATALL'
    BACKEND_PASSWORD = 'thisisbackend'

    # restrict access to a set of users
    USE_ALLOWED_USERS = False
    ALLOWED_USERS = []

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.abspath(DATABASE)

class ProductionConfig(Config):
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

class UnitTestConfig(Config):
    CSRF_ENABLED = False
    DATABASE = os.path.abspath('tests/data/copr.db')
    OPENID_STORE = os.path.abspath('tests/data/openid_store')

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.abspath(DATABASE)
