from datetime import datetime, timezone

from sqlalchemy.orm import synonym

from src.core.database import db
from src.core.timezone import ahora_ar

class VersionOferta(db.Model):
    __tablename__ = 'version_ofertas'

    id = db.Column(db.Integer, primary_key=True)
    id_version = synonym('id')
    id_oferta = db.Column(db.Integer, db.ForeignKey('ofertas.id'), nullable=False)
    numero_version = db.Column(db.Integer, nullable=False)
    fecha_version = db.Column(db.DateTime(timezone=True), default=lambda: ahora_ar(), nullable=False)
    usuario_modificacion = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    observaciones = db.Column(db.Text, nullable=True)
    estado_versiones = db.Column(db.String(30), nullable=True)
    estado_version = synonym('estado_versiones')

    oferta = db.relationship('Oferta', back_populates='versiones')

    detalles = db.relationship('DetalleVersionOferta', back_populates='version', cascade='all, delete-orphan')

    usuario = db.relationship('Usuario', foreign_keys=[usuario_modificacion])

    __table_args__ = (
        db.UniqueConstraint('id_oferta', 'numero_version', name='uq_oferta_version'),
    )

    def __repr__(self):
        return f'<VersionOferta {self.id_version} - Oferta: {self.id_oferta} - Version: {self.numero_version}>'