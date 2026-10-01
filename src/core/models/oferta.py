from datetime import datetime, timezone

from sqlalchemy.orm import synonym

from src.core.database import db
from src.core.enums import EstadoOfertaEnum

class Oferta(db.Model):
    __tablename__ = 'ofertas'

    id = db.Column(db.Integer, primary_key=True)
    id_oferta = synonym('id')
    id_emergencia = db.Column(db.Integer, db.ForeignKey('emergencias.id'), nullable=False, index=True)

    fecha_creacion = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    estado = db.Column(
        db.Enum(EstadoOfertaEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=EstadoOfertaEnum.PENDIENTE,
    )
    version_actual = db.Column(db.Integer, nullable=False, default=1)
    es_conjunta = db.Column(db.Boolean, nullable=False, default=False)
    fecha_ultima_modificacion = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    versiones = db.relationship('VersionOferta', back_populates='oferta', cascade='all, delete-orphan', order_by='VersionOferta.numero_version')
    emergencia = db.relationship('Emergencia', backref='ofertas')

    def __repr__(self):
        return f'<Oferta {self.id_oferta} - Estado: {self.estado}>'