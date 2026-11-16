"""Guardar la prioridad de las nuevas emergencias."""
from alembic import op
import sqlalchemy as sa

revision = "a6f92c1e473b"
down_revision = "d891aa72be10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("emergencias", sa.Column("prioridad", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("emergencias", "prioridad")
