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


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()

    tito_package_rows = session.execute(
            "SELECT * FROM package WHERE source_type=:param",
            {"param": 3})

    for package in tito_package_rows:
        source_dict = json.loads(package['source_json']) if package['source_json'] else {}
        new_source_dict = {
            'type': 'git',
            'clone_url': source_dict.get('git_url') or '',
            'committish': source_dict.get('git_branch') or '',
            'subdirectory': source_dict.get('git_dir') or '',
            'spec': '',
            'srpm_build_method': 'tito_test' if source_dict.get('tito_test') else 'tito',
        }
        new_source_json = json.dumps(new_source_dict)
        new_source_type = 8
        session.execute(
            "UPDATE package SET source_json=:param1, source_type=:param2 WHERE id=:param3",
            {"param1": new_source_json, "param2": new_source_type, "param3": package['id']})

    mock_package_rows = session.execute(
            "SELECT * FROM package WHERE source_type=:param",
            {"param": 4})

    for package in mock_package_rows:
        source_dict = json.loads(package['source_json']) if package['source_json'] else {}
        new_source_dict = {
            'type': source_dict.get('scm_type') or 'git',
            'clone_url': source_dict.get('scm_url') or '',
            'committish': source_dict.get('scm_branch') or '',
            'subdirectory': source_dict.get('scm_subdir') or '',
            'spec': source_dict.get('spec') or '',
            'srpm_build_method': 'rpkg',
        }
        new_source_json = json.dumps(new_source_dict)
        new_source_type = 8
        session.execute(
            "UPDATE package SET source_json=:param1, source_type=:param2 WHERE id=:param3",
            {"param1": new_source_json, "param2": new_source_type, "param3": package['id']})

    fedpkg_package_rows = session.execute(
            "SELECT * FROM package WHERE source_type=:param",
            {"param": 7})

    for package in fedpkg_package_rows:
        source_dict = json.loads(package['source_json']) if package['source_json'] else {}
        new_source_dict = {
            'type': 'git',
            'clone_url': source_dict.get('clone_url') or '',
            'committish': source_dict.get('branch') or '',
            'subdirectory': '',
            'spec': '',
            'srpm_build_method': 'rpkg',
        }
        new_source_json = json.dumps(new_source_dict)
        new_source_type = 8
        session.execute(
            "UPDATE package SET source_json=:param1, source_type=:param2 WHERE id=:param3",
            {"param1": new_source_json, "param2": new_source_type, "param3": package['id']})


def downgrade():
    pass
