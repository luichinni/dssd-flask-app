from src.core.database import db
from src.core.models.actividad import ActividadONG
from src.core.models.lote_necesidades import LoteNecesidades
from src.core.enums.estado_actividad_enum import EstadoActividadEnum
from src.core.timezone import ahora_ar

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
    lote_referencia = data.get('lote_referencia')
    if lote_referencia in ('', None):
        lote_referencia = None
    else:
        try:
            lote_referencia = int(lote_referencia)
        except (TypeError, ValueError) as error:
            raise ValueError('La referencia del lote debe ser un ID válido.') from error
        if db.session.get(LoteNecesidades, lote_referencia) is None:
            raise ValueError('El lote seleccionado no existe.')

    recursos_utilizados = data.get('recursos_utilizados')
    if isinstance(recursos_utilizados, str):
        recursos_utilizados = {'descripcion': recursos_utilizados.strip()} if recursos_utilizados.strip() else None

    actividad = ActividadONG(
        ong_id=ong_id,
        titulo=data.get('titulo', '').strip(),
        descripcion=data.get('descripcion', '').strip(),
        lote_referencia=lote_referencia,
        estado=EstadoActividadEnum.EN_EJECUCION,
        fecha_inicio=datetime.utcnow(),
        recursos_utilizados=recursos_utilizados,
    )
    db.session.add(actividad)
    db.session.commit()
    return actividad

def finalizar_actividad(actividad_id: int, ong_id: int, informe_cierre: str, recursos_utilizados: str = None):
    """Marca la actividad como finalizada, guarda el informe y la fecha de cierre.
    Si todas las actividades de la ONG para esa emergencia finalizaron (cierre total),
    notifica a Bonita para liberar los recursos comprometidos.
    """
    import logging
    from src.core.services.bonita import notificar_cierre_ong, BonitaError
    logger = logging.getLogger(__name__)

    actividad = obtener_actividad(actividad_id, ong_id)
    if not actividad:
        return None

    actividad.estado = EstadoActividadEnum.FINALIZADA
    actividad.fecha_finalizacion = ahora_ar()
    actividad.informe_cierre = informe_cierre.strip()
    if recursos_utilizados:
        actividad.recursos_utilizados = {'descripcion': recursos_utilizados.strip()}

    db.session.commit()

    # Si la actividad corresponde a una emergencia mediante lote_referencia, verificar cierre total
    if actividad.lote_referencia:
        lote = db.session.get(LoteNecesidades, actividad.lote_referencia)
        if lote and lote.emergencia:
            emergencia = lote.emergencia
            lote_ids = [l.id for l in emergencia.lotes]
            pendientes = ActividadONG.query.filter(
                ActividadONG.ong_id == ong_id,
                ActividadONG.lote_referencia.in_(lote_ids),
                ActividadONG.estado != EstadoActividadEnum.FINALIZADA,
            ).count()

            if pendientes == 0 and emergencia.bonita_case_id:
                try:
                    notificar_cierre_ong(emergencia.bonita_case_id, ong_id)
                    logger.info("Notificado cierre total de ONG %s para caso Bonita %s", ong_id, emergencia.bonita_case_id)
                except BonitaError as err:
                    logger.warning("No se pudo notificar a Bonita el fin de actividades de la ONG %s: %s", ong_id, err)

            pendientes_totales = ActividadONG.query.filter(
                ActividadONG.lote_referencia.in_(lote_ids),
                ActividadONG.estado != EstadoActividadEnum.FINALIZADA,
            ).count()
            if pendientes_totales == 0 and emergencia.bonita_case_id:
                emergencia.bonita_estado = "finalizada"
                db.session.commit()

    return actividad
