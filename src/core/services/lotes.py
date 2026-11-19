from datetime import datetime, timezone
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from src.core.database import db
from src.core.enums import EstadoOfertaEnum, RolEnum, TipoNotificacionEnum
from src.core.models.detalle_version_oferta import DetalleVersionOferta
from src.core.models.emergencia import Emergencia
from src.core.models.lote_detalle import LoteDetalle
from src.core.models.lote_necesidades import LoteNecesidades
from src.core.models.oferta import Oferta
from src.core.models.ong import ONG
from src.core.models.recurso_catalogo import RecursoCatalogo
from src.core.models.user import Usuario
from src.core.models.version_oferta import VersionOferta
from src.core.services.notificaciones import crear_notificacion
from src.core.services.bonita import BonitaError, completar_publicacion_lote
from src.core.timezone import ARGENTINA_TZ, ahora_ar

logger = logging.getLogger(__name__)

def _utc(fecha: datetime) -> datetime:
    return a_argentina(fecha)

def estado_lote(lote: LoteNecesidades, ahora: datetime = None) -> str:
    """Deriva el estado operativo usando fechas y detalles ya persistidos."""
    inicio = lote.fecha_inicio_ofertas
    cierre = lote.fecha_cierre_ofertas
    if not lote.detalles or inicio is None or cierre is None:
        return 'fallido'

    inicio = _utc(inicio)
    cierre = _utc(cierre)
    if cierre <= inicio:
        return 'fallido'

    ahora = _utc(ahora or ahora_ar())
    if inicio > ahora:
        return 'programado'
    if cierre <= ahora:
        return 'vencido'
    return 'publicado'


def listar_lotes():
    return (
        LoteNecesidades.query
        .options(
            joinedload(LoteNecesidades.emergencia),
            selectinload(LoteNecesidades.detalles).joinedload(LoteDetalle.recurso),
        )
        .order_by(LoteNecesidades.id.desc())
        .all()
    )


def listar_convocatorias_activas():
    ahora = func.now()
    return (
        LoteNecesidades.query
        .options(
            joinedload(LoteNecesidades.emergencia),
            selectinload(LoteNecesidades.detalles).joinedload(LoteDetalle.recurso),
        )
        .filter(
            LoteNecesidades.fecha_inicio_ofertas.isnot(None),
            LoteNecesidades.fecha_inicio_ofertas <= ahora,
            LoteNecesidades.fecha_cierre_ofertas > ahora,
            LoteNecesidades.detalles.any(),
        )
        .order_by(LoteNecesidades.fecha_cierre_ofertas.asc())
        .all()
    )


def obtener_lote(lote_id: int):
    return (
        LoteNecesidades.query
        .options(
            joinedload(LoteNecesidades.emergencia),
            selectinload(LoteNecesidades.detalles).joinedload(LoteDetalle.recurso),
        )
        .filter(LoteNecesidades.id == lote_id)
        .first()
    )


def _notificar_convocatoria(lote: LoteNecesidades, reabierta: bool = False) -> None:
    emergencia = lote.emergencia
    recursos = ', '.join(
        f'{detalle.recurso.nombre} (cantidad {detalle.cantidad_necesaria}, mínimo {detalle.cantidad_minima})'
        for detalle in lote.detalles
    )
    accion = 'reabierta' if reabierta else 'publicada'
    titulo = f'Convocatoria {accion}: lote #{lote.id}'
    mensaje = (
        f'La convocatoria #{lote.id} fue {accion} para la emergencia '
        f'#{emergencia.id} ({emergencia.zona_afectada}). Recursos solicitados: {recursos}.'
    )

    try:
        destinatarios = Usuario.query.filter_by(rol=RolEnum.ONG).all()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('No se pudieron consultar destinatarios para la convocatoria CCR %s', lote.id)
        return

    for usuario in destinatarios:
        ong_id = (usuario.datos_adicionales or {}).get('ong_id')
        if ong_id is None:
            continue
        try:
            if db.session.get(ONG, int(ong_id)) is None:
                continue
            crear_notificacion(
                usuario_id=usuario.id,
                titulo=titulo,
                mensaje=mensaje,
                tipo=TipoNotificacionEnum.CONVOCATORIA,
                referencia_id=lote.id,
            )
        except SQLAlchemyError:
            db.session.rollback()
            logger.exception('No se pudo notificar la convocatoria CCR %s al usuario %s', lote.id, usuario.id)


def cantidades_ofertadas_por_recurso(emergencia_id: int) -> dict[int, int]:
    filas = (
        db.session.query(
            DetalleVersionOferta.id_recurso,
            func.sum(DetalleVersionOferta.cantidad),
        )
        .join(VersionOferta, VersionOferta.id == DetalleVersionOferta.id_version)
        .join(Oferta, Oferta.id == VersionOferta.id_oferta)
        .filter(
            Oferta.id_emergencia == emergencia_id,
            Oferta.estado != EstadoOfertaEnum.RECHAZADA,
            VersionOferta.numero_version == Oferta.version_actual,
        )
        .group_by(DetalleVersionOferta.id_recurso)
        .all()
    )
    return {recurso_id: int(cantidad) for recurso_id, cantidad in filas}


def evaluar_minimos_lote(lote: LoteNecesidades, cantidades_ofertadas: dict[int, int]) -> list[dict]:
    necesidades = {}
    for detalle in lote.detalles:
        recurso_id = detalle.id_recurso or detalle.recurso.id
        necesidad = necesidades.setdefault(recurso_id, {
            'recurso': detalle.recurso,
            'cantidad_necesaria': 0,
            'cantidad_minima': 0,
        })
        necesidad['cantidad_necesaria'] += detalle.cantidad_necesaria
        necesidad['cantidad_minima'] += detalle.cantidad_minima

    evaluacion = []
    for recurso_id, necesidad in necesidades.items():
        cant_r = cantidades_ofertadas.get(recurso_id, 0)
        min_r = necesidad['cantidad_minima']
        evaluacion.append({
            'recurso': necesidad['recurso'],
            'cantidad_necesaria': necesidad['cantidad_necesaria'],
            'cant_r': cant_r,
            'min_r': min_r,
            'alcanzado': cant_r >= min_r,
        })
    return evaluacion


def lote_requiere_decision(lote: LoteNecesidades, cantidades_ofertadas: dict[int, int]) -> bool:
    if estado_lote(lote) != 'vencido':
        return False
    return any(not item['alcanzado'] for item in evaluar_minimos_lote(lote, cantidades_ofertadas))


def _validar_decision_pendiente(lote_id: int):
    lote = db.session.get(LoteNecesidades, lote_id)
    if lote is None:
        raise ValueError('El lote seleccionado no existe.')

    cantidades = cantidades_ofertadas_por_recurso(lote.emergencia_id)
    evaluacion = evaluar_minimos_lote(lote, cantidades)
    if estado_lote(lote) != 'vencido' or not any(not item['alcanzado'] for item in evaluacion):
        raise ValueError('El lote no venció con cantidades mínimas pendientes.')
    return lote, cantidades, evaluacion


def reabrir_convocatoria(lote_id: int, fecha_cierre_ofertas: datetime) -> LoteNecesidades:
    lote, _, _ = _validar_decision_pendiente(lote_id)
    ahora = ahora_ar()
    fecha_cierre_ofertas = _utc(fecha_cierre_ofertas)
    if fecha_cierre_ofertas <= ahora:
        raise ValueError('La fecha de cierre debe ser posterior a la reapertura.')

    lote.fecha_inicio_ofertas = ahora
    lote.fecha_cierre_ofertas = fecha_cierre_ofertas
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    _notificar_convocatoria(lote, reabierta=True)
    return lote


def reformular_lote(lote_id: int, detalles: list[dict], fecha_cierre_ofertas: datetime) -> LoteNecesidades:
    lote, _, _ = _validar_decision_pendiente(lote_id)
    if not detalles:
        raise ValueError('Agrega al menos un recurso al lote reformulado.')

    detalles_validados = []
    recurso_ids = set()
    for detalle in detalles:
        try:
            recurso_id = int(detalle['recurso_id'])
            cantidad_necesaria = int(detalle['cantidad_necesaria'])
            min_r = int(detalle['min_r'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Completa recurso, cantidad y mínimo requerido para cada fila.') from error
        if recurso_id in recurso_ids:
            raise ValueError('No repitas un recurso en el lote reformulado.')
        recurso_ids.add(recurso_id)
        recurso = db.session.get(RecursoCatalogo, recurso_id)
        if recurso is None:
            raise ValueError('Uno de los recursos seleccionados no existe.')
        if cantidad_necesaria < 1 or min_r < 1 or min_r > cantidad_necesaria:
            raise ValueError('Las cantidades deben cumplir 1 <= min_r <= cantidad necesaria.')
        detalles_validados.append((recurso, cantidad_necesaria, min_r))

    ahora = ahora_ar()
    fecha_cierre_ofertas = _utc(fecha_cierre_ofertas)
    if fecha_cierre_ofertas <= ahora:
        raise ValueError('La fecha de cierre debe ser posterior a la reformulación.')

    lote.detalles.clear()
    for recurso, cantidad_necesaria, min_r in detalles_validados:
        lote.detalles.append(LoteDetalle(
            recurso=recurso,
            cantidad_necesaria=cantidad_necesaria,
            cantidad_minima=min_r,
        ))
    lote.fecha_inicio_ofertas = ahora
    lote.fecha_cierre_ofertas = fecha_cierre_ofertas
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    _notificar_convocatoria(lote, reabierta=True)
    return lote


def continuar_con_ofertas_disponibles(lote_id: int) -> int:
    lote, _, evaluacion = _validar_decision_pendiente(lote_id)
    recurso_ids = [item['recurso'].id for item in evaluacion if not item['alcanzado']]
    ofertas = (
        Oferta.query
        .join(VersionOferta, (VersionOferta.id_oferta == Oferta.id) &
              (VersionOferta.numero_version == Oferta.version_actual))
        .join(DetalleVersionOferta, DetalleVersionOferta.id_version == VersionOferta.id)
        .filter(
            Oferta.id_emergencia == lote.emergencia_id,
            Oferta.estado != EstadoOfertaEnum.RECHAZADA,
            DetalleVersionOferta.id_recurso.in_(recurso_ids),
        )
        .distinct()
        .all()
    )
    if not ofertas:
        raise ValueError('No hay ofertas disponibles para continuar con el lote.')

    pendientes = [oferta for oferta in ofertas if oferta.estado == EstadoOfertaEnum.PENDIENTE]
    for oferta in pendientes:
        oferta.estado = EstadoOfertaEnum.ACEPTADA
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return len(pendientes)


def emergencia_activa(emergencia: Emergencia, ahora: datetime = None) -> bool:
    """Una emergencia permanece activa mientras no se hayan cerrado todos sus lotes."""
    ahora = ahora or ahora_ar()
    if not emergencia.lotes:
        return True

    for lote in emergencia.lotes:
        fecha_cierre = lote.fecha_cierre_ofertas
        if fecha_cierre is None:
            return True
        if _utc(fecha_cierre) > _utc(ahora):
            return True
    return False


def listar_emergencias():
    return (
        Emergencia.query
        .options(selectinload(Emergencia.lotes))
        .order_by(Emergencia.fecha_registro.desc())
        .all()
    )


def listar_emergencias_activas():
    emergencias = listar_emergencias()
    ahora = ahora_ar()
    return [emergencia for emergencia in emergencias if emergencia_activa(emergencia, ahora)]


def publicar_lote(emergencia_id: int, detalles: list[dict],
                  fecha_cierre_ofertas: datetime) -> LoteNecesidades:
    emergencia = db.session.get(Emergencia, emergencia_id)
    if emergencia is None or not emergencia_activa(emergencia):
        raise ValueError('La emergencia seleccionada no existe o ya no está activa.')

    if not detalles:
        raise ValueError('Agrega al menos un recurso al lote.')

    detalles_validados = []
    for detalle in detalles:
        try:
            recurso_id = int(detalle['recurso_id'])
            cantidad_necesaria = int(detalle['cantidad_necesaria'])
            min_r = int(detalle['min_r'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Completa recurso, cantidad y mínimo requerido para cada fila.') from error

        recurso = db.session.get(RecursoCatalogo, recurso_id)
        if recurso is None:
            raise ValueError('Uno de los recursos seleccionados no existe.')
        if cantidad_necesaria < 1 or min_r < 1 or min_r > cantidad_necesaria:
            raise ValueError('Las cantidades deben cumplir 1 <= min_r <= cantidad necesaria.')
        detalles_validados.append((recurso, cantidad_necesaria, min_r))
    """""
    ahora = ahora_ar()
    if fecha_cierre_ofertas.tzinfo is None:
        fecha_cierre_ofertas = fecha_cierre_ofertas.replace(tzinfo=ARGENTINA_TZ)
    if fecha_cierre_ofertas <= ahora:
        raise ValueError('La fecha de cierre debe ser posterior a la publicación.')
    """""
    ahora = ahora_ar()
    # Convertimos la fecha ingresada localmente a su instante UTC real
    fecha_cierre_ofertas = _utc(fecha_cierre_ofertas)
    
    if fecha_cierre_ofertas <= ahora:
        raise ValueError('La fecha de cierre debe ser posterior a la publicación.')
    
    try:
        lote = LoteNecesidades(
            emergencia_id=emergencia.id,
            fecha_inicio_ofertas=ahora,
            fecha_cierre_ofertas=fecha_cierre_ofertas,
        )
        db.session.add(lote)
        for recurso, cantidad_necesaria, min_r in detalles_validados:
            lote.detalles.append(LoteDetalle(
                recurso=recurso,
                cantidad_necesaria=cantidad_necesaria,
                cantidad_minima=min_r,
            ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    # Serializar los avances BPM de esta emergencia. El lote ya está guardado:
    # no revertir datos locales si una llamada externa tiene resultado incierto.
    try:
        emergencia = Emergencia.query.filter_by(id=emergencia.id).with_for_update().one()
        if emergencia.bonita_case_id is None:
            raise BonitaError("La emergencia no tiene un caso Bonita confirmado.")
        #completar_publicacion_lote(emergencia.bonita_case_id, emergencia.id, lote.fecha_cierre_ofertas)
        completar_publicacion_lote(emergencia.bonita_case_id, emergencia.id, fecha_cierre_ofertas)
    except BonitaError as error:
        lote.bonita_estado = "no_confirmado"
        logger.warning("No se confirmó la publicación del lote %s en Bonita: %s", lote.id, error)
    else:
        lote.bonita_estado = "sincronizado"
    db.session.commit()
    _notificar_convocatoria(lote)
    return lote


def reintentar_lote(lote_id: int, fecha_cierre_ofertas: datetime,
                    recurso_id: int = None, cantidad_necesaria: int = None,
                    min_r: int = None) -> LoteNecesidades:
    lote = db.session.get(LoteNecesidades, lote_id)
    if lote is None:
        raise ValueError('El lote seleccionado no existe.')

    estado = estado_lote(lote)
    if estado != 'fallido':
        raise ValueError('Solo se pueden reintentar lotes fallidos; los vencidos requieren una decisión CCR.')

    ahora = ahora_ar()
    fecha_cierre_ofertas = _utc(fecha_cierre_ofertas)
    if fecha_cierre_ofertas <= ahora:
        raise ValueError('La fecha de cierre debe ser posterior a la reapertura.')

    if not lote.detalles:
        if recurso_id is None or cantidad_necesaria is None or min_r is None:
            raise ValueError('El lote fallido requiere recurso, cantidad y mínimo requerido.')
        recurso = db.session.get(RecursoCatalogo, recurso_id)
        if recurso is None:
            raise ValueError('El recurso seleccionado no existe.')
        if cantidad_necesaria < 1 or min_r < 1 or min_r > cantidad_necesaria:
            raise ValueError('Las cantidades deben cumplir 1 <= min_r <= cantidad necesaria.')
        lote.detalles.append(LoteDetalle(
            recurso=recurso,
            cantidad_necesaria=cantidad_necesaria,
            cantidad_minima=min_r,
        ))

    lote.fecha_inicio_ofertas = ahora
    lote.fecha_cierre_ofertas = fecha_cierre_ofertas
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return lote

def todos_los_lotes_cubiertos(emergencia_id: int) -> bool:
    """Verifica si todos los lotes de la emergencia tienen sus mínimos alcanzados."""
    emergencia = db.session.get(Emergencia, emergencia_id)
    if emergencia is None:
        raise ValueError('La emergencia seleccionada no existe.')

    cantidades = cantidades_ofertadas_por_recurso(emergencia.id)
    for lote in emergencia.lotes:
        if lote.detalles and lote.fecha_inicio_ofertas and lote.fecha_cierre_ofertas:
            evaluacion = evaluar_minimos_lote(lote, cantidades)
            if any(not item['alcanzado'] for item in evaluacion):
                return False
    return True