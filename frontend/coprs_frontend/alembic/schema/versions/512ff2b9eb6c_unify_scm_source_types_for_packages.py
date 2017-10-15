"""unify scm source types for packages

Revision ID: 512ff2b9eb6c
Revises: a8654abcec65
Create Date: 2017-10-14 13:24:44.164388

"""

# revision identifiers, used by Alembic.
revision = '512ff2b9eb6c'
down_revision = 'a8654abcec65'

from alembic import op
import sqlalchemy as sa
import json

from coprs import models

def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()

    for package in session.query(models.Package).filter(models.Package.source_type == 3):
        source_dict = package.source_json_dict
        new_source_dict = {
            'type': 'git',
            'clone_url': source_dict.get('git_url') or '',
            'committish': source_dict.get('git_branch') or '',
            'subdirectory': source_dict.get('git_dir') or '',
            'spec': '',
            'srpm_build_method': 'tito_test' if source_dict.get('tito_test') else 'tito',
        }
        package.source_json = json.dumps(new_source_dict)
        package.source_type = 8
        session.add(package)

    for package in session.query(models.Package).filter(models.Package.source_type == 4):
        source_dict = package.source_json_dict
        new_source_dict = {
            'type': source_dict.get('scm_type') or 'git',
            'clone_url': source_dict.get('scm_url') or '',
            'committish': source_dict.get('scm_branch') or '',
            'subdirectory': '',
            'spec': source_dict.get('spec') or '',
            'srpm_build_method': 'rpkg',
        }
        package.source_json = json.dumps(new_source_dict)
        package.source_type = 8
        session.add(package)

    for package in session.query(models.Package).filter(models.Package.source_type == 7):
        source_dict = package.source_json_dict
        new_source_dict = {
            'type': 'git',
            'clone_url': source_dict.get('clone_url') or '',
            'committish': source_dict.get('branch') or '',
            'subdirectory': '',
            'spec': '',
            'srpm_build_method': 'rpkg',
        }
        package.source_json = json.dumps(new_source_dict)
        package.source_type = 8
        session.add(package)

    session.commit()


def downgrade():
    pass
