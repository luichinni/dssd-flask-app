from src.core.database import db
from src.core.models.emergencia import Emergencia

def listar_emergencias(reportante_id: int):
    """Devuelve todas las emergencias registradas por reportante, si no tiene emergencias devuelve una lista vacía."""
    return Emergencia.query.filter_by(reportante_id=reportante_id).order_by(Emergencia.created_at.desc()).all()
