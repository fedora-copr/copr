"""add indexes

Revision ID: 20140423001
Revises: 5845661bb37d
Create Date: 2014-04-24 11:25:36.216132

"""

# revision identifiers, used by Alembic.
revision = '20140423001'
down_revision = '5845661bb37d'

from alembic import op


def upgrade():
    op.create_index('build_ended_on_canceled_started_on', 'build', ['ended_on', 'canceled', 'started_on'])
    op.create_index('copr_owner_id', 'copr', ['owner_id'])
    op.create_index('copr_deleted_name', 'copr', ['deleted', 'name'])
    op.create_index('copr_chroot_copr_id', 'copr_chroot', ['copr_id'])
    op.create_index('action_result_action_type', 'action', ['result', 'action_type']) 
    op.create_index('user_openid_name', 'user', ['openid_name'])
    op.create_index('copr_permission_copr_id', 'copr_permission', ['copr_id'])
    op.create_index('build_chroot_build_id', 'build_chroot', ['build_id'])
    op.create_index('user_api_login', 'user', ['api_login'])
    op.create_index('legal_flag_resolved_on', 'legal_flag', ['resolved_on'])

def downgrade():
    op.drop_index('build_ended_on_canceled_started_on')
    op.drop_index('copr_owner_id')
    op.drop_index('copr_deleted_name')
    op.drop_index('copr_chroot_copr_id')
    op.drop_index('action_result_action_type')
    op.drop_index('user_openid_name')
    op.drop_index('copr_permission_copr_id')
    op.drop_index('build_chroot_build_id')
    op.drop_index('user_api_login')
    op.drop_index('legal_flag_resolved_on')


