from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from src.core.database import db
from src.core.enums import EstadoActividadEnum
from src.core.timezone import ahora_ar

class ActividadONG(db.Model):
    __tablename__ = 'actividades_ong'

    id = db.Column(db.Integer, primary_key=True)
    ong_id = db.Column(db.Integer, db.ForeignKey('ongs.id'), nullable=False, index=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    lote_referencia = db.Column(db.Integer, db.ForeignKey('lotes_necesidades.id'), nullable=True)
    estado = db.Column(
        db.Enum(EstadoActividadEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=EstadoActividadEnum.EN_EJECUCION,
    )
    fecha_inicio = db.Column(db.DateTime(timezone=True), default=lambda: ahora_ar(), nullable=False)
    fecha_finalizacion = db.Column(db.DateTime(timezone=True), nullable=True)
    informe_cierre = db.Column(db.Text, nullable=True)
    recursos_utilizados = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: ahora_ar(), nullable=False)

    ong = db.relationship('ONG', back_populates='actividades')
    lote = db.relationship('LoteNecesidades', back_populates='actividades')

    def __repr__(self):
        return f'<ActividadONG {self.id}: {self.titulo} - {self.estado.value}>'
