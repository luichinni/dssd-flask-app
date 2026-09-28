from datetime import datetime
from src.core.database import db

class VersionOferta(db.Model):
    __tablename__ = 'version_ofertas'

    id_version = db.Column(db.Integer, primary_key=True)
    id_oferta = db.Column(db.Integer, db.ForeignKey('ofertas.id_oferta'), nullable=False)
    numero_version = db.Column(db.Integer, nullable=False)
    fecha_version = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_modificacion = db.Column(db.Integer(20), db.ForeignKey('usuarios.id'), nullable=True)
    observaciones = db.Column(db.Text, nullable=True)
    estado_version = db.Column(db.String(30), nullable=False, default='pendiente')

    oferta = db.relationship('Oferta', back_populates='versiones')

    detalles = db.relationship('DetalleVersionOferta', back_populates='version', cascade='all, delete-orphan')

    usuario = db.relationship('Usuario', foreign_keys=[usuario_modificacion])

    __table_args__ = (
        db.UniqueConstraint('id_oferta', 'numero_version', name='uq_oferta_version'),
    )

    def __repr__(self):
        return f'<VersionOferta {self.id_version} - Oferta: {self.id_oferta} - Version: {self.numero_version}>'