from datetime import datetime, timezone

from sqlalchemy.orm import synonym

from src.core.database import db
from src.core.enums import EstadoOfertaEnum
from src.core.timezone import ahora_ar

class Oferta(db.Model):
    __tablename__ = 'ofertas'

    id = db.Column(db.Integer, primary_key=True)
    id_oferta = synonym('id')
    id_emergencia = db.Column(db.Integer, db.ForeignKey('emergencias.id'), nullable=False, index=True)
    convocatoria_id = db.Column(db.Integer, db.ForeignKey('lotes_necesidades.id'), nullable=True, index=True)
    creada_por_ong_id = db.Column(db.Integer, db.ForeignKey('ongs.id'), nullable=True, index=True)

    fecha_creacion = db.Column(db.DateTime(timezone=True), default=lambda: ahora_ar(), nullable=False)
    estado = db.Column(
        db.Enum(EstadoOfertaEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=EstadoOfertaEnum.PENDIENTE,
    )
    version_actual = db.Column(db.Integer, nullable=False, default=1)
    es_conjunta = db.Column(db.Boolean, nullable=False, default=False)
    fecha_ultima_modificacion = db.Column(db.DateTime(timezone=True), default=lambda: ahora_ar(), onupdate=lambda: ahora_ar(), nullable=False)

    versiones = db.relationship('VersionOferta', back_populates='oferta', cascade='all, delete-orphan', order_by='VersionOferta.numero_version')
    emergencia = db.relationship('Emergencia', backref='ofertas')
    convocatoria = db.relationship('LoteNecesidades', backref='ofertas')
    participaciones = db.relationship('OfertaParticipante', back_populates='oferta', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Oferta {self.id_oferta} - Estado: {self.estado}>'