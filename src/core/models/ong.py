from src.core.database import db


class ONG(db.Model):
    __tablename__ = 'ongs'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

    inventarios = db.relationship('InventarioONG', back_populates='ong', cascade='all, delete-orphan')
    actividades = db.relationship('ActividadONG', back_populates='ong', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ONG {self.nombre}>'