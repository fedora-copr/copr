"""
Add namespace for fedora distgit

Revision ID: e2b1cb42e6b7
Revises: efec6b1aa9a2
Create Date: 2021-05-23 19:21:36.626784
"""

import sqlalchemy as sa
from alembic import op


revision = 'e2b1cb42e6b7'
down_revision = '8ea94673d6ee'


def _update(name, uri, namespace=None):
    sql = ("UPDATE dist_git_instance "
           "SET clone_package_uri=:uri, default_namespace=:namespace "
           "WHERE name=:name")
    conn = op.get_bind()
    conn.execute(sa.text(sql), name=name, uri=uri, namespace=namespace)


def upgrade():
    op.add_column(
        "dist_git_instance",
        sa.Column("default_namespace", sa.String(50), nullable=True)
    )
    _update(name="fedora", uri="{namespace}/rpms/{pkgname}.git", namespace="")


def downgrade():
    _update(name="fedora", uri="rpms/{pkgname}.git")
    op.drop_column("dist_git_instance", "default_namespace")
