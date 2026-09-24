from datetime import datetime
from src.core.database import db
from src.core.enums import TipoRecursoEnum

class InventarioONG(db.Model):
    __tablename__ = 'inventario_ong'

    id = db.Column(db.Integer, primary_key=True)
    ong_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    nombre = db.Column(db.String(120), nullable=False)
    tipo_recurso = db.Column(
        db.Enum(TipoRecursoEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    unidad_medida = db.Column(db.String(50), nullable=False, default="Unidades")
    cantidad_total = db.Column(db.Integer, nullable=False, default=0)
    cantidad_disponible = db.Column(db.Integer, nullable=False, default=0)
    descripcion = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    ong = db.relationship('Usuario', backref=db.backref('inventario', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<InventarioONG {self.nombre} ({self.cantidad_disponible}/{self.cantidad_total} {self.unidad_medida})>'
