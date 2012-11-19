import os

REPO_DIR = ''
if 'OPENSHIFT_REPO_DIR' in os.environ:
    REPO_DIR = os.environ['OPENSHIFT_REPO_DIR']

DATA_DIR = ''
if 'OPENSHIFT_DATA_DIR' in os.environ:
    DATA_DIR = os.environ['OPENSHIFT_DATA_DIR']

class Config(object):
    DATABASE = os.path.join(REPO_DIR, '../data/copr.db')
    OPENID_STORE = os.path.join(DATA_DIR, '../openid_store')
    SECRET_KEY = 'THISISNOTASECRETATALL'
    BACKEND_PASSWORD = 'thisisbackend'

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.abspath(DATABASE)

class ProductionConfig(Config):
    pass

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

class UnitTestConfig(Config):
    DATABASE = os.path.abspath('tests/data/copr.db')
    OPENID_STORE = os.path.abspath('tests/data/openid_store')

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.abspath(DATABASE)
