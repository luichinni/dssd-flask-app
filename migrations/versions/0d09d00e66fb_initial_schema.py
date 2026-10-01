"""initial schema

Revision ID: 0d09d00e66fb
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0d09d00e66fb'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('municipios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=150), nullable=False),
    sa.Column('provincia', sa.String(length=150), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ongs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=150), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('recursos_catalogo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.Column('tipo_recursos', sa.Enum('Personal', 'Insumo', 'Vehículo', 'Equipamiento', name='tiporecursoenum'), nullable=False),
    sa.Column('unidad_medida', sa.String(length=50), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=128), nullable=False),
    sa.Column('datos_adicionales', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('rol', sa.Enum('Operador Municipal', 'Centro Coordinador', 'ONG', 'Auditor', name='rolenum'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usuarios_email'), ['email'], unique=True)

    op.create_table('emergencias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tipo_desastre', sa.Enum('Geológico', 'Meteorológico', 'Hidrológico', 'Biológico', 'Incendio Forestal', name='tipodesastreenum'), nullable=False),
    sa.Column('nivel_gravedad', sa.Integer(), nullable=False),
    sa.Column('zona_afectada', sa.String(length=100), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.Column('responsable_id', sa.Integer(), nullable=False),
    sa.Column('municipio_id', sa.Integer(), nullable=False),
    sa.Column('fecha_registro', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipios.id'], ),
    sa.ForeignKeyConstraint(['responsable_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('emergencias', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_emergencias_municipio_id'), ['municipio_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_emergencias_responsable_id'), ['responsable_id'], unique=False)

    op.create_table('inventario_ong',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ong_id', sa.Integer(), nullable=False),
    sa.Column('id_recurso', sa.Integer(), nullable=False),
    sa.Column('cantidad_total', sa.Integer(), nullable=False),
    sa.Column('cantidad_disponible', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['id_recurso'], ['recursos_catalogo.id'], ),
    sa.ForeignKeyConstraint(['ong_id'], ['ongs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('inventario_ong', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inventario_ong_id_recurso'), ['id_recurso'], unique=False)
        batch_op.create_index(batch_op.f('ix_inventario_ong_ong_id'), ['ong_id'], unique=False)

    op.create_table('notificaciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('mensaje', sa.Text(), nullable=False),
    sa.Column('tipo', sa.Enum('Adjudicación de Lote', 'Convocatoria', 'Sistema', name='tiponotificacionenum'), nullable=False),
    sa.Column('referencia_id', sa.Integer(), nullable=True),
    sa.Column('leida', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notificaciones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notificaciones_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('lotes_necesidades',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('emergencia_id', sa.Integer(), nullable=False),
    sa.Column('fecha_inicio_ofertas', sa.DateTime(timezone=True), nullable=True),
    sa.Column('fecha_cierre_ofertas', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['emergencia_id'], ['emergencias.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lotes_necesidades', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lotes_necesidades_emergencia_id'), ['emergencia_id'], unique=False)

    op.create_table('ofertas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('id_emergencia', sa.Integer(), nullable=False),
    sa.Column('fecha_creacion', sa.DateTime(timezone=True), nullable=False),
    sa.Column('estado', sa.Enum('Pendiente', 'Aceptada', 'Rechazada', 'Adjudicada', name='estadoofertaenum'), nullable=False),
    sa.Column('version_actual', sa.Integer(), nullable=False),
    sa.Column('es_conjunta', sa.Boolean(), nullable=False),
    sa.Column('fecha_ultima_modificacion', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['id_emergencia'], ['emergencias.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ofertas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ofertas_id_emergencia'), ['id_emergencia'], unique=False)

    op.create_table('actividades_ong',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ong_id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.Column('lote_referencia', sa.Integer(), nullable=True),
    sa.Column('estado', sa.Enum('En Ejecución', 'Finalizada', name='estadoactividadenum'), nullable=False),
    sa.Column('fecha_inicio', sa.DateTime(timezone=True), nullable=False),
    sa.Column('fecha_finalizacion', sa.DateTime(timezone=True), nullable=True),
    sa.Column('informe_cierre', sa.Text(), nullable=True),
    sa.Column('recursos_utilizados', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['lote_referencia'], ['lotes_necesidades.id'], ),
    sa.ForeignKeyConstraint(['ong_id'], ['ongs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('actividades_ong', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_actividades_ong_ong_id'), ['ong_id'], unique=False)

    op.create_table('lote_detalles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lote_id', sa.Integer(), nullable=False),
    sa.Column('id_recurso', sa.Integer(), nullable=False),
    sa.Column('cantidad_necesaria', sa.Integer(), nullable=False),
    sa.Column('cantidad_minima', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['id_recurso'], ['recursos_catalogo.id'], ),
    sa.ForeignKeyConstraint(['lote_id'], ['lotes_necesidades.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lote_detalles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lote_detalles_lote_id'), ['lote_id'], unique=False)

    op.create_table('version_ofertas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('id_oferta', sa.Integer(), nullable=False),
    sa.Column('numero_version', sa.Integer(), nullable=False),
    sa.Column('fecha_version', sa.DateTime(timezone=True), nullable=False),
    sa.Column('usuario_modificacion', sa.Integer(), nullable=False),
    sa.Column('observaciones', sa.Text(), nullable=True),
    sa.Column('estado_versiones', sa.String(length=30), nullable=True),
    sa.ForeignKeyConstraint(['id_oferta'], ['ofertas.id'], ),
    sa.ForeignKeyConstraint(['usuario_modificacion'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_oferta', 'numero_version', name='uq_oferta_version')
    )
    op.create_table('detalle_version_oferta',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('id_version', sa.Integer(), nullable=False),
    sa.Column('id_ong', sa.Integer(), nullable=False),
    sa.Column('id_recurso', sa.Integer(), nullable=False),
    sa.Column('cantidad', sa.Integer(), nullable=False),
    sa.Column('cantidad_adjudicada', sa.Integer(), nullable=False),
    sa.CheckConstraint('cantidad > 0', name='chk_cantidad_positiva'),
    sa.CheckConstraint('cantidad_adjudicada >= 0 AND cantidad_adjudicada <= cantidad', name='chk_cantidad_adjudicada'),
    sa.ForeignKeyConstraint(['id_ong'], ['ongs.id'], ),
    sa.ForeignKeyConstraint(['id_recurso'], ['recursos_catalogo.id'], ),
    sa.ForeignKeyConstraint(['id_version'], ['version_ofertas.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_version', 'id_ong', 'id_recurso', name='uq_version_ong_recurso')
    )


def downgrade():
    op.drop_table('detalle_version_oferta')
    op.drop_table('version_ofertas')
    op.drop_table('lote_detalles')
    op.drop_table('actividades_ong')
    op.drop_table('ofertas')
    op.drop_table('lotes_necesidades')
    op.drop_table('notificaciones')
    op.drop_table('inventario_ong')
    op.drop_table('emergencias')
    op.drop_table('usuarios')
    op.drop_table('recursos_catalogo')
    op.drop_table('ongs')
    op.drop_table('municipios')