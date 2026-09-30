from datetime import datetime, timezone
from src.core.database import db
from src.core.enums import TipoNotificacionEnum

class Notificacion(db.Model):
    __tablename__ = 'notificaciones'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    titulo = db.Column(db.String(200), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    tipo = db.Column(
        db.Enum(TipoNotificacionEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TipoNotificacionEnum.ADJUDICACION_LOTE,
    )
    referencia_id = db.Column(db.Integer, nullable=True)
    leida = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    usuario = db.relationship('Usuario', backref=db.backref('notificaciones', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<Notificacion {self.id}: {self.titulo} (Leída: {self.leida})>'
