from src.core.database import db
from src.core.models.notificacion import Notificacion
from src.core.enums.notificacion_enum import TipoNotificacionEnum

def listar_notificaciones(usuario_id: int, solo_no_leidas: bool = False):
    """Devuelve las notificaciones del usuario ordenadas de más reciente a más antigua."""
    query = Notificacion.query.filter_by(usuario_id=usuario_id)
    if solo_no_leidas:
        query = query.filter_by(leida=False)
    return query.order_by(Notificacion.created_at.desc()).all()

def obtener_notificacion(notificacion_id: int, usuario_id: int):
    """Obtiene una notificación asegurando que corresponda al usuario."""
    return Notificacion.query.filter_by(id=notificacion_id, usuario_id=usuario_id).first()

def marcar_leida(notificacion_id: int, usuario_id: int) -> bool:
    """Marca una notificación como leída."""
    notif = obtener_notificacion(notificacion_id, usuario_id)
    if not notif:
        return False
    notif.leida = True
    db.session.commit()
    return True

def marcar_todas_leidas(usuario_id: int) -> int:
    """Marca todas las notificaciones pendientes del usuario como leídas."""
    pendientes = Notificacion.query.filter_by(usuario_id=usuario_id, leida=False).all()
    for notif in pendientes:
        notif.leida = True
    db.session.commit()
    return len(pendientes)

def contar_no_leidas(usuario_id: int) -> int:
    """Cuenta las notificaciones no leídas."""
    return Notificacion.query.filter_by(usuario_id=usuario_id, leida=False).count()

def crear_notificacion(usuario_id: int, titulo: str, mensaje: str, tipo=TipoNotificacionEnum.ADJUDICACION_LOTE, referencia_id=None):
    """Crea una nueva notificación para un usuario."""
    notif = Notificacion(
        usuario_id=usuario_id,
        titulo=titulo,
        mensaje=mensaje,
        tipo=tipo,
        referencia_id=referencia_id,
        leida=False,
    )
    db.session.add(notif)
    db.session.commit()
    return notif
