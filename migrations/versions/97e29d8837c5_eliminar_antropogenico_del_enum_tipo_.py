"""eliminar antropogenico del enum tipo_desastre

Revision ID: 97e29d8837c5
Revises: 1d1d44ba1961
Create Date: 2026-09-28 23:15:21.115306

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '97e29d8837c5'
down_revision = '1d1d44ba1961'
branch_labels = None
depends_on = None


def upgrade():
    # No reclasificamos "Incendio Forestal": queda como categoría propia
    # No hay filas con "Antropogénico", así que no hace falta reasignar nada

    op.execute(
        "CREATE TYPE tipodesastreenum_new AS ENUM "
        "('Geológico', 'Meteorológico', 'Hidrológico', 'Biológico', 'Incendio Forestal')"
    )
    op.execute(
        "ALTER TABLE emergencias "
        "ALTER COLUMN tipo_desastre TYPE tipodesastreenum_new "
        "USING tipo_desastre::text::tipodesastreenum_new"
    )
    op.execute("DROP TYPE tipodesastreenum")
    op.execute("ALTER TYPE tipodesastreenum_new RENAME TO tipodesastreenum")


def downgrade():
    op.execute(
        "CREATE TYPE tipodesastreenum_old AS ENUM "
        "('Geológico', 'Meteorológico', 'Hidrológico', 'Biológico', 'Antropogénico')"
    )
    # Ojo: las filas con "Incendio Forestal" no tienen equivalente en el tipo viejo.
    # Hay que decidir a qué reasignarlas antes de cambiar el tipo de la columna.
    op.execute(
        "UPDATE emergencias SET tipo_desastre = 'Meteorológico' "
        "WHERE tipo_desastre = 'Incendio Forestal'"
    )
    op.execute(
        "ALTER TABLE emergencias "
        "ALTER COLUMN tipo_desastre TYPE tipodesastreenum_old "
        "USING tipo_desastre::text::tipodesastreenum_old"
    )
    op.execute("DROP TYPE tipodesastreenum")
    op.execute("ALTER TYPE tipodesastreenum_old RENAME TO tipodesastreenum")