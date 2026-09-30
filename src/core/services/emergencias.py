from src.core.database import db
from src.core.models.emergencia import Emergencia

def listar_emergencias(reportante_id: int):
    """Devuelve todas las emergencias registradas por reportante, si no tiene emergencias devuelve una lista vacía."""
    return Emergencia.query.filter_by(reportante_id=reportante_id).order_by(Emergencia.created_at.desc()).all()


def crear_emergencia(tipo_desastre: str, nivel_gravedad: str, zona_afectada: str, descripcion: str, reportante_id: int):
    """Crea una nueva emergencia y la guarda en la base de datos."""
    nueva_emergencia = Emergencia(

        tipo_desastre=tipo_desastre,
        nivel_gravedad=nivel_gravedad,
        zona_afectada=zona_afectada,
        descripcion=descripcion,
        reportante_id=reportante_id
    )
    db.session.add(nueva_emergencia)
    db.session.commit()
    return nueva_emergencia

def listar_todas_las_emergencias():
    """Devuelve todas las emergencias disponibles para que una ONG pueda realizar una oferta."""
    return Emergencia.query.order_by(Emergencia.created_at.desc()).all()