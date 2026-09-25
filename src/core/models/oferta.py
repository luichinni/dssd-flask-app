from datetime import datetime
from src.core.database import db

class Oferta(db.Model):
    __tablename__ = 'ofertas'

    id_oferta = db.Column(db.Integer, primary_key=True)
    id_emergencia = db.Column(db.Integer, nullable=False)

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(20), nullable=False, default='pendiente')
    version_actual = db.Column(db.Integer, nullable=False, default=1)
    es_conjunta = db.Column(db.Boolean, nullable=False, default=False)
    fecha_ultima_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    versiones = db.relationship('VersionOferta', back_populates='oferta', cascade='all, delete-orphan', order_by='VersionOferta.numero_version')

    def __repr__(self):
        return f'<Oferta {self.id_oferta} - Estado: {self.estado}>'