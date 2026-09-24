from datetime import datetime
from src.core.database import db
from src.core.models.actividad import ActividadONG
from src.core.enums.estado_actividad_enum import EstadoActividadEnum

def listar_actividades(ong_id: int, estado: EstadoActividadEnum = None):
    """Devuelve las actividades de la ONG, opcionalmente filtradas por estado."""
    query = ActividadONG.query.filter_by(ong_id=ong_id)
    if estado:
        query = query.filter_by(estado=estado)
    return query.order_by(ActividadONG.created_at.desc()).all()

def obtener_actividad(actividad_id: int, ong_id: int):
    """Obtiene una actividad garantizando que pertenezca a la ONG."""
    return ActividadONG.query.filter_by(id=actividad_id, ong_id=ong_id).first()

def crear_actividad(ong_id: int, data: dict):
    """Crea una nueva actividad operativa para la ONG."""
    actividad = ActividadONG(
        ong_id=ong_id,
        titulo=data.get('titulo', '').strip(),
        descripcion=data.get('descripcion', '').strip(),
        lote_referencia=data.get('lote_referencia', '').strip(),
        estado=EstadoActividadEnum.EN_EJECUCION,
        fecha_inicio=datetime.utcnow(),
        recursos_utilizados=data.get('recursos_utilizados', '').strip(),
    )
    db.session.add(actividad)
    db.session.commit()
    return actividad

def finalizar_actividad(actividad_id: int, ong_id: int, informe_cierre: str, recursos_utilizados: str = None):
    """Marca la actividad como finalizada, guarda el informe y la fecha de cierre."""
    actividad = obtener_actividad(actividad_id, ong_id)
    if not actividad:
        return None

    actividad.estado = EstadoActividadEnum.FINALIZADA
    actividad.fecha_finalizacion = datetime.utcnow()
    actividad.informe_cierre = informe_cierre.strip()
    if recursos_utilizados:
        actividad.recursos_utilizados = recursos_utilizados.strip()

    db.session.commit()
    return actividad
