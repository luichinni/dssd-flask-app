from datetime import datetime, timezone

from sqlalchemy.orm import joinedload, selectinload

from src.core.database import db
from src.core.models.emergencia import Emergencia
from src.core.models.lote_detalle import LoteDetalle
from src.core.models.lote_necesidades import LoteNecesidades
from src.core.models.recurso_catalogo import RecursoCatalogo


def _utc(fecha: datetime) -> datetime:
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


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

    ahora = _utc(ahora or datetime.now(timezone.utc))
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


def emergencia_activa(emergencia: Emergencia, ahora: datetime = None) -> bool:
    """Una emergencia permanece activa mientras no se hayan cerrado todos sus lotes."""
    ahora = ahora or datetime.now(timezone.utc)
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
    ahora = datetime.now(timezone.utc)
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

    ahora = datetime.now(timezone.utc)
    if fecha_cierre_ofertas.tzinfo is None:
        fecha_cierre_ofertas = fecha_cierre_ofertas.replace(tzinfo=timezone.utc)
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
    return lote


def reintentar_lote(lote_id: int, fecha_cierre_ofertas: datetime,
                    recurso_id: int = None, cantidad_necesaria: int = None,
                    min_r: int = None) -> LoteNecesidades:
    lote = db.session.get(LoteNecesidades, lote_id)
    if lote is None:
        raise ValueError('El lote seleccionado no existe.')

    estado = estado_lote(lote)
    if estado not in ('fallido', 'vencido'):
        raise ValueError('Solo se pueden reintentar lotes fallidos o reabrir lotes vencidos.')

    ahora = datetime.now(timezone.utc)
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