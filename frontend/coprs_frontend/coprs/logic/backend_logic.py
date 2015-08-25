# coding: utf-8

import json
from sqlalchemy import or_
from sqlalchemy import and_
from sqlalchemy.sql import false

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers

from coprs.logic.coprs_logic import MockChrootsLogic

log = app.logger


class BackendLogic(object):
    pass
