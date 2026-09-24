from datetime import datetime
from src.core.database import db
from src.core.enums import EstadoActividadEnum

class ActividadONG(db.Model):
    __tablename__ = 'actividades_ong'

    id = db.Column(db.Integer, primary_key=True)
    ong_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    lote_referencia = db.Column(db.String(100), nullable=True)
    estado = db.Column(
        db.Enum(EstadoActividadEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=EstadoActividadEnum.EN_EJECUCION,
    )
    fecha_inicio = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_finalizacion = db.Column(db.DateTime, nullable=True)
    informe_cierre = db.Column(db.Text, nullable=True)
    recursos_utilizados = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ong = db.relationship('Usuario', backref=db.backref('actividades', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<ActividadONG {self.id}: {self.titulo} - {self.estado.value}>'
