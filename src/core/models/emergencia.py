from datetime import datetime, timezone

from sqlalchemy.orm import synonym

from src.core.database import db
from src.core.enums import TipoDesastreEnum, NivelGravedadEnum
from src.core.timezone import ahora_ar

class Emergencia(db.Model):
    __tablename__ = 'emergencias'

    id = db.Column(db.Integer, primary_key=True)
    tipo_desastre = db.Column(db.Enum(TipoDesastreEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    nivel_gravedad = db.Column(db.Integer, nullable=False, default=NivelGravedadEnum.BAJO.value)
    zona_afectada = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    responsable_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    fecha_registro = db.Column(db.DateTime(timezone=True), default=lambda: ahora_ar(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: ahora_ar(), onupdate=lambda: ahora_ar(), nullable=False)

    bonita_case_id = db.Column(db.BigInteger, nullable=True, unique=True)
    bonita_estado = db.Column(db.String(20), nullable=False, default="sin_iniciar", server_default="sin_iniciar")

    reportante_id = synonym('responsable_id')
    created_at = synonym('fecha_registro')
    responsable = db.relationship('Usuario', foreign_keys=[responsable_id], backref='emergencias_reportadas')
    municipio = db.relationship('Municipio', back_populates='emergencias')
    lotes = db.relationship('LoteNecesidades', back_populates='emergencia', cascade='all, delete-orphan')

    #Relacion con los lotes asociados a la emergencia (pendiente por hacer)