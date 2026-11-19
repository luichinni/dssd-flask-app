from datetime import datetime, timezone

from src.core.database import db
from src.core.timezone import ahora_ar


class OfertaParticipante(db.Model):
    __tablename__ = 'ofertas_participantes'

    id = db.Column(db.Integer, primary_key=True)
    oferta_id = db.Column(db.Integer, db.ForeignKey('ofertas.id'), nullable=False, index=True)
    ong_id = db.Column(db.Integer, db.ForeignKey('ongs.id'), nullable=False, index=True)
    estado = db.Column(db.String(20), nullable=False, default='Pendiente')
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: ahora_ar(),
    )

    oferta = db.relationship('Oferta', back_populates='participaciones')
    ong = db.relationship('ONG')

    __table_args__ = (
        db.UniqueConstraint('oferta_id', 'ong_id', name='uq_oferta_participante'),
    )