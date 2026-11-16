from src.core.database import db
from src.core.models.emergencia import Emergencia
from src.core.services.bonita import BonitaError, _ClienteBonita, iniciar_proceso
from src.core.services.prioridades import obtener_prioridad
from flask import current_app

def listar_emergencias(reportante_id: int):
    """Devuelve todas las emergencias registradas por reportante, si no tiene emergencias devuelve una lista vacía."""
    return Emergencia.query.filter_by(reportante_id=reportante_id).order_by(Emergencia.created_at.desc()).all()


def crear_emergencia(tipo_desastre: str, nivel_gravedad: int, zona_afectada: str, descripcion: str, reportante_id: int, municipio_id: int):
    """Guarda la emergencia y crea su caso BPM, sin reintentos automáticos."""
    prioridad = obtener_prioridad(nivel_gravedad, zona_afectada)
    nueva_emergencia = Emergencia(
        tipo_desastre=tipo_desastre,
        nivel_gravedad=nivel_gravedad,
        zona_afectada=zona_afectada,
        prioridad=prioridad,
        descripcion=descripcion,
        responsable_id=reportante_id,
        municipio_id=municipio_id,
    )
    nueva_emergencia.bonita_estado = "iniciando"
    db.session.add(nueva_emergencia)
    db.session.commit()

    # El ID local debe existir antes de iniciar un proceso externo.
    # Conservar la emergencia permite investigar resultados inciertos sin
    # crear otra emergencia/caso automáticamente.
    try:
        nueva_emergencia.bonita_case_id = iniciar_proceso(
            {"id_emergencia_init": nueva_emergencia.id}
        )
        # Avanzar la primer tarea donde se reciben los datos de la emergencia
        _ClienteBonita().completar(
            nueva_emergencia.bonita_case_id,
            "Registrar emergencia",
            {"id_emergencia_input": nueva_emergencia.id}
        )
    except BonitaError as error:
        nueva_emergencia.bonita_estado = "no_confirmado"
        db.session.commit()
        current_app.logger.warning(
            "No se confirmó el caso de la emergencia %s: %s",
            nueva_emergencia.id, error,
        )
    else:
        nueva_emergencia.bonita_estado = "vinculada"
        db.session.commit()
    return nueva_emergencia

def listar_todas_las_emergencias():
    """Devuelve todas las emergencias disponibles para que una ONG pueda realizar una oferta."""
    return Emergencia.query.order_by(Emergencia.created_at.desc()).all()
