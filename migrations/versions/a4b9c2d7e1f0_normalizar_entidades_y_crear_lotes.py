"""Normaliza ONG, catálogo e inventario; agrega municipio, lotes y ofertas.

Revision ID: a4b9c2d7e1f0
Revises: 97e29d8837c5
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'a4b9c2d7e1f0'
down_revision = '97e29d8837c5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'municipios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('provincia', sa.String(length=150), nullable=False),
    )
    op.create_table(
        'ongs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
    )
    op.create_table(
        'recursos_catalogo',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('tipo_recursos', postgresql.ENUM(name='tiporecursoenum', create_type=False), nullable=False),
        sa.Column('unidad_medida', sa.String(length=50), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
    )

    op.execute("""
        INSERT INTO ongs (id, nombre, descripcion)
        SELECT DISTINCT u.id,
               COALESCE(u.datos_adicionales->>'organizacion', u.nombre),
               u.datos_adicionales->>'personeria'
        FROM usuarios AS u
        WHERE u.rol::text = 'ONG'
           OR u.id IN (SELECT ong_id FROM inventario_ong)
           OR u.id IN (SELECT ong_id FROM actividades_ong)
    """)
    op.execute("""
        UPDATE usuarios AS u
        SET datos_adicionales = jsonb_build_object('ong_id', u.id)
        WHERE u.rol::text = 'ONG'
          AND EXISTS (SELECT 1 FROM ongs AS o WHERE o.id = u.id)
    """)
    op.execute("""
        SELECT setval(pg_get_serial_sequence('ongs', 'id'),
                      COALESCE((SELECT MAX(id) FROM ongs), 1),
                      EXISTS (SELECT 1 FROM ongs))
    """)

    op.add_column('inventario_ong', sa.Column('id_recurso', sa.Integer(), nullable=True))
    connection = op.get_bind()
    for row in connection.execute(sa.text("""
        SELECT id, nombre, tipo_recurso::text AS tipo_recurso, unidad_medida, descripcion
        FROM inventario_ong ORDER BY id
    """)):
        catalog_id = connection.execute(sa.text("""
            INSERT INTO recursos_catalogo (nombre, tipo_recursos, unidad_medida, descripcion)
            VALUES (:nombre, CAST(:tipo AS tiporecursoenum), :unidad, :descripcion)
            RETURNING id
        """), {
            'nombre': row.nombre,
            'tipo': row.tipo_recurso,
            'unidad': row.unidad_medida,
            'descripcion': row.descripcion,
        }).scalar_one()
        connection.execute(
            sa.text('UPDATE inventario_ong SET id_recurso = :catalog_id WHERE id = :inventory_id'),
            {'catalog_id': catalog_id, 'inventory_id': row.id},
        )

    op.drop_constraint('inventario_ong_ong_id_fkey', 'inventario_ong', type_='foreignkey')
    op.create_foreign_key('fk_inventario_ong_ong_id_ongs', 'inventario_ong', 'ongs', ['ong_id'], ['id'])
    op.create_foreign_key('fk_inventario_ong_recurso_catalogo', 'inventario_ong', 'recursos_catalogo', ['id_recurso'], ['id'])
    op.alter_column('inventario_ong', 'id_recurso', nullable=False)
    op.create_index('ix_inventario_ong_id_recurso', 'inventario_ong', ['id_recurso'])
    op.drop_column('inventario_ong', 'nombre')
    op.drop_column('inventario_ong', 'tipo_recurso')
    op.drop_column('inventario_ong', 'unidad_medida')
    op.drop_column('inventario_ong', 'descripcion')

    op.drop_constraint('actividades_ong_ong_id_fkey', 'actividades_ong', type_='foreignkey')
    op.create_foreign_key('fk_actividades_ong_ong_id_ongs', 'actividades_ong', 'ongs', ['ong_id'], ['id'])
    op.alter_column('actividades_ong', 'lote_referencia', new_column_name='lote_referencia_legacy')
    op.add_column('actividades_ong', sa.Column('lote_referencia', sa.Integer(), nullable=True))
    op.alter_column('actividades_ong', 'recursos_utilizados', type_=postgresql.JSONB(), postgresql_using='to_jsonb(recursos_utilizados)')
    for column in ('fecha_inicio', 'fecha_finalizacion', 'created_at'):
        op.alter_column('actividades_ong', column, type_=sa.DateTime(timezone=True), postgresql_using=f"{column} AT TIME ZONE 'UTC'")
    for column in ('created_at', 'updated_at'):
        op.alter_column('inventario_ong', column, type_=sa.DateTime(timezone=True), postgresql_using=f"{column} AT TIME ZONE 'UTC'")
    op.alter_column('notificaciones', 'created_at', type_=sa.DateTime(timezone=True), postgresql_using="created_at AT TIME ZONE 'UTC'")

    op.execute("INSERT INTO municipios (nombre, provincia) VALUES ('Sin asignar', 'Sin asignar')")
    op.execute("""
        UPDATE usuarios
        SET datos_adicionales = jsonb_build_object(
            'municipio_id', (SELECT id FROM municipios WHERE nombre = 'Sin asignar' AND provincia = 'Sin asignar')
        )
        WHERE rol::text = 'Operador Municipal'
    """)
    op.alter_column('emergencias', 'reportante_id', new_column_name='responsable_id')
    op.alter_column('emergencias', 'created_at', new_column_name='fecha_registro')
    op.alter_column('emergencias', 'fecha_registro', type_=sa.DateTime(timezone=True), postgresql_using="fecha_registro AT TIME ZONE 'UTC'")
    op.alter_column('emergencias', 'updated_at', type_=sa.DateTime(timezone=True), postgresql_using="updated_at AT TIME ZONE 'UTC'")
    op.alter_column('emergencias', 'descripcion', type_=sa.Text(), nullable=True)
    op.drop_index('ix_emergencias_reportante_id', table_name='emergencias')
    op.create_index('ix_emergencias_responsable_id', 'emergencias', ['responsable_id'])
    op.add_column('emergencias', sa.Column('municipio_id', sa.Integer(), nullable=True))
    op.execute("UPDATE emergencias SET municipio_id = (SELECT id FROM municipios WHERE nombre = 'Sin asignar' AND provincia = 'Sin asignar')")
    op.alter_column('emergencias', 'municipio_id', nullable=False)
    op.create_foreign_key('fk_emergencias_municipio_id', 'emergencias', 'municipios', ['municipio_id'], ['id'])
    op.create_index('ix_emergencias_municipio_id', 'emergencias', ['municipio_id'])

    op.create_table(
        'lotes_necesidades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('emergencia_id', sa.Integer(), nullable=False, index=True),
        sa.Column('fecha_inicio_ofertas', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_cierre_ofertas', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['emergencia_id'], ['emergencias.id']),
    )
    op.create_table(
        'lote_detalles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lote_id', sa.Integer(), nullable=False, index=True),
        sa.Column('id_recurso', sa.Integer(), nullable=False),
        sa.Column('cantidad_necesaria', sa.Integer(), nullable=False),
        sa.Column('cantidad_minima', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['lote_id'], ['lotes_necesidades.id']),
        sa.ForeignKeyConstraint(['id_recurso'], ['recursos_catalogo.id']),
    )
    op.create_foreign_key('fk_actividades_ong_lote_referencia', 'actividades_ong', 'lotes_necesidades', ['lote_referencia'], ['id'])

    op.create_table(
        'ofertas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('id_emergencia', sa.Integer(), nullable=False, index=True),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), nullable=False),
        sa.Column('estado', sa.Enum('Pendiente', 'Aceptada', 'Rechazada', 'Adjudicada', name='estadoofertaenum'), nullable=False),
        sa.Column('version_actual', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('es_conjunta', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('fecha_ultima_modificacion', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['id_emergencia'], ['emergencias.id']),
    )
    op.create_table(
        'version_ofertas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('id_oferta', sa.Integer(), nullable=False),
        sa.Column('numero_version', sa.Integer(), nullable=False),
        sa.Column('fecha_version', sa.DateTime(timezone=True), nullable=False),
        sa.Column('usuario_modificacion', sa.Integer(), nullable=False),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('estado_versiones', sa.String(length=30), nullable=True),
        sa.ForeignKeyConstraint(['id_oferta'], ['ofertas.id']),
        sa.ForeignKeyConstraint(['usuario_modificacion'], ['usuarios.id']),
        sa.UniqueConstraint('id_oferta', 'numero_version', name='uq_oferta_version'),
    )
    op.create_table(
        'detalle_version_oferta',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('id_version', sa.Integer(), nullable=False),
        sa.Column('id_ong', sa.Integer(), nullable=False),
        sa.Column('id_recurso', sa.Integer(), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False),
        sa.Column('cantidad_adjudicada', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['id_version'], ['version_ofertas.id']),
        sa.ForeignKeyConstraint(['id_ong'], ['ongs.id']),
        sa.ForeignKeyConstraint(['id_recurso'], ['recursos_catalogo.id']),
        sa.CheckConstraint('cantidad > 0', name='chk_cantidad_positiva'),
        sa.CheckConstraint('cantidad_adjudicada >= 0 AND cantidad_adjudicada <= cantidad', name='chk_cantidad_adjudicada'),
    )


def downgrade():
    op.drop_table('detalle_version_oferta')
    op.drop_table('version_ofertas')
    op.drop_table('ofertas')
    postgresql.ENUM(name='estadoofertaenum').drop(op.get_bind(), checkfirst=True)
    op.drop_constraint('fk_actividades_ong_lote_referencia', 'actividades_ong', type_='foreignkey')
    op.drop_table('lote_detalles')
    op.drop_table('lotes_necesidades')

    op.drop_constraint('fk_emergencias_municipio_id', 'emergencias', type_='foreignkey')
    op.drop_index('ix_emergencias_municipio_id', table_name='emergencias')
    op.drop_column('emergencias', 'municipio_id')
    op.drop_index('ix_emergencias_responsable_id', table_name='emergencias')
    op.alter_column('emergencias', 'descripcion', type_=sa.String(length=255), nullable=False)
    op.alter_column('emergencias', 'fecha_registro', new_column_name='created_at')
    op.alter_column('emergencias', 'responsable_id', new_column_name='reportante_id')
    op.create_index('ix_emergencias_reportante_id', 'emergencias', ['reportante_id'])

    op.alter_column('actividades_ong', 'recursos_utilizados', type_=sa.Text(), postgresql_using='recursos_utilizados::text')
    op.drop_column('actividades_ong', 'lote_referencia')
    op.alter_column('actividades_ong', 'lote_referencia_legacy', new_column_name='lote_referencia')
    op.drop_constraint('fk_actividades_ong_ong_id_ongs', 'actividades_ong', type_='foreignkey')
    op.create_foreign_key('actividades_ong_ong_id_fkey', 'actividades_ong', 'usuarios', ['ong_id'], ['id'])
    for column in ('fecha_inicio', 'fecha_finalizacion', 'created_at'):
        op.alter_column('actividades_ong', column, type_=sa.DateTime(), postgresql_using=f"{column} AT TIME ZONE 'UTC'")
    for column in ('created_at', 'updated_at'):
        op.alter_column('inventario_ong', column, type_=sa.DateTime(), postgresql_using=f"{column} AT TIME ZONE 'UTC'")
    op.alter_column('notificaciones', 'created_at', type_=sa.DateTime(), postgresql_using="created_at AT TIME ZONE 'UTC'")

    op.add_column('inventario_ong', sa.Column('nombre', sa.String(length=120), nullable=True))
    op.add_column('inventario_ong', sa.Column('tipo_recurso', postgresql.ENUM(name='tiporecursoenum', create_type=False), nullable=True))
    op.add_column('inventario_ong', sa.Column('unidad_medida', sa.String(length=50), nullable=True))
    op.add_column('inventario_ong', sa.Column('descripcion', sa.Text(), nullable=True))
    op.execute("""
        UPDATE inventario_ong AS i
        SET nombre = r.nombre, tipo_recurso = r.tipo_recursos,
            unidad_medida = r.unidad_medida, descripcion = r.descripcion
        FROM recursos_catalogo AS r WHERE i.id_recurso = r.id
    """)
    op.alter_column('inventario_ong', 'nombre', nullable=False)
    op.alter_column('inventario_ong', 'tipo_recurso', nullable=False)
    op.alter_column('inventario_ong', 'unidad_medida', nullable=False)
    op.drop_constraint('fk_inventario_ong_recurso_catalogo', 'inventario_ong', type_='foreignkey')
    op.drop_index('ix_inventario_ong_id_recurso', table_name='inventario_ong')
    op.drop_column('inventario_ong', 'id_recurso')
    op.drop_constraint('fk_inventario_ong_ong_id_ongs', 'inventario_ong', type_='foreignkey')
    op.create_foreign_key('inventario_ong_ong_id_fkey', 'inventario_ong', 'usuarios', ['ong_id'], ['id'])

    op.drop_table('recursos_catalogo')
    op.drop_table('ongs')
    op.drop_table('municipios')