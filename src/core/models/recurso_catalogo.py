from src.core.database import db
from src.core.enums import TipoRecursoEnum


class RecursoCatalogo(db.Model):
    __tablename__ = 'recursos_catalogo'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    tipo_recursos = db.Column(
        db.Enum(TipoRecursoEnum, values_callable=lambda enum: [item.value for item in enum]),
        nullable=False,
    )
    unidad_medida = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

    inventarios = db.relationship('InventarioONG', back_populates='recurso')
    detalles_oferta = db.relationship('DetalleVersionOferta', back_populates='recurso')
    detalles_lote = db.relationship('LoteDetalle', back_populates='recurso')

    def __repr__(self):
        return f'<RecursoCatalogo {self.nombre}>'