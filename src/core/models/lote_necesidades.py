from src.core.database import db


class LoteNecesidades(db.Model):
    __tablename__ = 'lotes_necesidades'

    id = db.Column(db.Integer, primary_key=True)
    emergencia_id = db.Column(db.Integer, db.ForeignKey('emergencias.id'), nullable=False, index=True)
    fecha_inicio_ofertas = db.Column(db.DateTime(timezone=True), nullable=True)
    fecha_cierre_ofertas = db.Column(db.DateTime(timezone=True), nullable=True)

    emergencia = db.relationship('Emergencia', back_populates='lotes')
    detalles = db.relationship('LoteDetalle', back_populates='lote', cascade='all, delete-orphan')
    actividades = db.relationship('ActividadONG', back_populates='lote')

    def __repr__(self):
        return f'<LoteNecesidades {self.id} - Emergencia: {self.emergencia_id}>'