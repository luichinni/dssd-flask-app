"""Vincular emergencias con casos Bonita.

Revision ID: c17e82ba4102
Revises: ab2143139b53
"""
from alembic import op
import sqlalchemy as sa

revision = "c17e82ba4102"
down_revision = "ab2143139b53"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("emergencias", sa.Column("bonita_case_id", sa.BigInteger(), nullable=True))
    op.add_column("emergencias", sa.Column("bonita_estado", sa.String(20), nullable=False, server_default="sin_iniciar"))
    op.create_unique_constraint("uq_emergencias_bonita_case_id", "emergencias", ["bonita_case_id"])


def downgrade():
    op.drop_constraint("uq_emergencias_bonita_case_id", "emergencias", type_="unique")
    op.drop_column("emergencias", "bonita_estado")
    op.drop_column("emergencias", "bonita_case_id")
