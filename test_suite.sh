#!/bin/sh
find . -path '*/__pycache__' | xargs rm -rfv

#pip install --user virtualenv

virtualenv _venv
source _venv/bin/activate

pip install  pytest mock pytest-cov sphinx flask flask-script SQLAlchemy==0.8.7 flask-whooshee Flask-OpenID Flask-SQLAlchemy==1.0  Flask-WTF blinker pytz markdown pyLibravatar pydns  flexmock whoosh decorator


cp -rv /usr/lib/python2.7/site-packages/rpmUtils _venv/lib/python2.7/site-packages/
cp -rv /usr/lib64/python2.7/site-packages/rpm _venv/lib/python2.7/site-packages/

pip install -r python/requirements.txt
pip install -r cli/requirements.txt
pip install -r frontend/requirements.txt


python -m pytest python/copr  --junitxml=python-copr.junit.xml --cov-report xml --cov python/copr/client

PYTHONPATH=python/:cli/:$PYTHONPATH  python -m pytest cli/tests --junitxml=cli.junit.xml --cov-report xml --cov cli/copr_cli

COPR_CONFIG="$(pwd)/frontend/coprs_frontend/config/copr_unit_test.conf"  \
    python -m pytest frontend/coprs_frontend/tests --junitxml=frontend.junit.xml --cov-report xml --cov frontend/coprs_frontend/coprs

deactivate


