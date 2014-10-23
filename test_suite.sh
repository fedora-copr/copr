#!/bin/sh
find . -path '*/__pycache__' | xargs rm -rfv

#pip install --user virtualenv

virtualenv _venv
source _venv/bin/activate


# sphinx flask flask-script SQLAlchemy==0.8.7 flask-whooshee Flask-OpenID Flask-SQLAlchemy==1.0  Flask-WTF blinker pytz markdown pyLibravatar pydns  flexmock whoosh decorator
pip install  pytest mock pytest-cov  ipdb redis bunch PyYAML


cp -rv /usr/lib/python2.7/site-packages/rpmUtils _venv/lib/python2.7/site-packages/
cp -rv /usr/lib64/python2.7/site-packages/rpm _venv/lib/python2.7/site-packages/

pip install -r python/requirements.txt
pip install -r cli/requirements.txt
pip install -r frontend/requirements.txt
pip install -r backend/requirements.txt
pip install -r keygen/requirements.txt


mkdir -p _report

COPR_CONFIG="$(pwd)/frontend/coprs_frontend/config/copr_unit_test.conf"  \
    python -m pytest frontend/coprs_frontend/tests --junitxml=_report/frontend.junit.xml --cov-report xml --cov frontend/coprs_frontend/coprs $@
mv {,_report/frontend.}coverage.xml

PYTHONPATH=backend/run:backend:python:$PYTHONPATH python -m pytest backend/tests  --junitxml=_report/backend.junit.xml --cov-report xml --cov backend/backend $@
mv {,_report/backend.}coverage.xml

python -m pytest python/copr/test  --junitxml=_report/python-copr.junit.xml --cov-report xml --cov python/copr/client $@
mv {,_report/python-copr.}coverage.xml

PYTHONPATH=python/:cli/:$PYTHONPATH  python -m pytest cli/tests --junitxml=_report/cli.junit.xml --cov-report xml --cov cli/copr_cli $@
mv {,_report/cli.}coverage.xml

PYTHONPATH=keygen/src:$PYTHONPATH python -B -m pytest keygen/tests  --junitxml=_report/keygen.junit.xml --cov-report xml --cov keygen/src $@
mv {,_report/keygen.}coverage.xml

deactivate
rm -rf _tmp/*

