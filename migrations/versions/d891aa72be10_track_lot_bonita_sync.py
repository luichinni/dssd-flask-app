"""Registrar sincronización de lotes con Bonita."""
from alembic import op
import sqlalchemy as sa

revision = "d891aa72be10"
down_revision = "c17e82ba4102"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("lotes_necesidades", sa.Column("bonita_estado", sa.String(20), nullable=False, server_default="sin_sincronizar"))


def downgrade():
    op.drop_column("lotes_necesidades", "bonita_estado")
