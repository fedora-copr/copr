"""unify-scm-source-types

Revision ID: a8654abcec65
Revises: fdec9947f8a1
Create Date: 2017-10-13 14:49:22.183416

"""

# revision identifiers, used by Alembic.
revision = 'a8654abcec65'
down_revision = 'fdec9947f8a1'

from alembic import op
import sqlalchemy as sa
import json


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()

    tito_build_rows = session.execute(
            "SELECT * FROM build WHERE source_type=:param",
            {"param": 3})

    for build in tito_build_rows:
        source_dict = json.loads(build['source_json']) if build['source_json'] else {}
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
            "UPDATE build SET source_json=:param1, source_type=:param2 WHERE id=:param3",
            {"param1": new_source_json, "param2": new_source_type, "param3": build['id']})

    mock_build_rows = session.execute(
            "SELECT * FROM build WHERE source_type=:param",
            {"param": 4})

    for build in mock_build_rows:
        source_dict = json.loads(build['source_json']) if build['source_json'] else {}
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
            "UPDATE build SET source_json=:param1, source_type=:param2 WHERE id=:param3",
            {"param1": new_source_json, "param2": new_source_type, "param3": build['id']})

    fedpkg_build_rows = session.execute(
            "SELECT * FROM build WHERE source_type=:param",
            {"param": 7})

    for build in fedpkg_build_rows:
        source_dict = json.loads(build['source_json']) if build['source_json'] else {}
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
            "UPDATE build SET source_json=:param1, source_type=:param2 WHERE id=:param3",
            {"param1": new_source_json, "param2": new_source_type, "param3": build['id']})


def downgrade():
    pass
