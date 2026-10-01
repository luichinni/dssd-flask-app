from datetime import datetime, timezone

from src.core.database import db

class InventarioONG(db.Model):
    __tablename__ = 'inventario_ong'

    id = db.Column(db.Integer, primary_key=True)
    ong_id = db.Column(db.Integer, db.ForeignKey('ongs.id'), nullable=False, index=True)
    id_recurso = db.Column(db.Integer, db.ForeignKey('recursos_catalogo.id'), nullable=False, index=True)
    cantidad_total = db.Column(db.Integer, nullable=False, default=0)
    cantidad_disponible = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    ong = db.relationship('ONG', back_populates='inventarios')
    recurso = db.relationship('RecursoCatalogo', back_populates='inventarios')

    @property
    def nombre(self):
        return self.recurso.nombre

    @nombre.setter
    def nombre(self, value):
        self.recurso.nombre = value

    @property
    def tipo_recurso(self):
        return self.recurso.tipo_recursos

    @tipo_recurso.setter
    def tipo_recurso(self, value):
        self.recurso.tipo_recursos = value

    @property
    def unidad_medida(self):
        return self.recurso.unidad_medida

    @unidad_medida.setter
    def unidad_medida(self, value):
        self.recurso.unidad_medida = value

    @property
    def descripcion(self):
        return self.recurso.descripcion

    @descripcion.setter
    def descripcion(self, value):
        self.recurso.descripcion = value

    def __repr__(self):
        return f'<InventarioONG {self.nombre} ({self.cantidad_disponible}/{self.cantidad_total} {self.unidad_medida})>'
