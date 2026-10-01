from src.core.database import db


class Municipio(db.Model):
    __tablename__ = 'municipios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    provincia = db.Column(db.String(150), nullable=False)

    emergencias = db.relationship('Emergencia', back_populates='municipio')

    def __repr__(self):
        return f'<Municipio {self.nombre}, {self.provincia}>'