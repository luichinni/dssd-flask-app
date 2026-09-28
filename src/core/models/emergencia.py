from src.core.database import db
from src.core.enums import TipoDesastreEnum, NivelGravedadEnum
from datetime import datetime

class Emergencia(db.Model):
    __tablename__ = 'emergencias'

    id = db.Column(db.Integer, primary_key=True)
    tipo_desastre = db.Column(db.Enum(TipoDesastreEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    nivel_gravedad = db.Column(db.Integer, nullable=False, default=NivelGravedadEnum.BAJO.value)
    zona_afectada = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(255), nullable=False) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False) #la hora la calcula py
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    #Relacion 1 a N con el usuario que reporta la emergencia
    reportante_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    reportante = db.relationship('Usuario', foreign_keys=[reportante_id], backref=db.backref('emergencias_reportadas', lazy=True))

    #Relacion con los lotes asociados a la emergencia (pendiente por hacer)