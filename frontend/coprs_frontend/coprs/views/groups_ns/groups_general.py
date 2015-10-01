# coding: utf-8

import os
import time
import os
import re
import urlparse

import flask
from flask import render_template
import platform
import smtplib
import sqlalchemy
from email.mime.text import MIMEText
from itertools import groupby

from coprs import app
from coprs import db
from coprs import rcp
from coprs import exceptions
from coprs import forms
from coprs import helpers
from coprs import models
from coprs.forms import group_managed_form_fabric
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.stat_logic import CounterStatLogic
from coprs.logic.users_logic import UsersLogic
from coprs.rmodels import TimedStatEvents

from coprs.logic.complex_logic import ComplexLogic

from coprs.views.misc import login_required, page_not_found

from coprs.views.coprs_ns import coprs_ns

from coprs.logic import builds_logic, coprs_logic, actions_logic, users_logic
from coprs.helpers import parse_package_name, generate_repo_url, CHROOT_RPMS_DL_STAT_FMT, CHROOT_REPO_MD_DL_STAT_FMT


@coprs_ns.route("/groups/activate/<fas_group>", methods=["GET", "POST"])
@login_required
def activate_group(fas_group):
    pass


@coprs_ns.route("/groups/by_user/<username>")
def list_groups_by_user(username):
    pass
