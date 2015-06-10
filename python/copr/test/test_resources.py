# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from copr.client.responses import ProjectWrapper

def test_project_wrapper_unicode():
    project = ProjectWrapper("<client>", "<username>", "<projectname>",
                             description="ěščřžýáíé",
                             instructions="ěščřžýáíé")
    assert str(project)
