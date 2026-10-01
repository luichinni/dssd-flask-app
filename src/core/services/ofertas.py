from datetime import datetime

from src.core.database import db
from src.core.models.oferta import Oferta
from src.core.models.version_oferta import VersionOferta
from src.core.models.detalle_version_oferta import DetalleVersionOferta
from src.core.models.inventario import InventarioONG
from src.core.enums import EstadoOfertaEnum
from src.core.models.emergencia import Emergencia
from src.core.models.ong import ONG
from src.core.models.user import Usuario
from src.core.models.lote_necesidades import LoteNecesidades
from src.core.models.oferta_participante import OfertaParticipante
from src.core.enums import RolEnum, TipoNotificacionEnum
from src.core.services.notificaciones import crear_notificacion


def listar_ongs_colaboradoras(ong_id):
    usuarios_ong = Usuario.query.filter_by(rol=RolEnum.ONG).all()
    usuario_por_ong = {}
    for usuario in usuarios_ong:
        try:
            perfil_id = int((usuario.datos_adicionales or {}).get('ong_id'))
        except (TypeError, ValueError):
            continue
        usuario_por_ong[perfil_id] = usuario

    return [
        {
            'ong': ong,
            'usuario': usuario_por_ong[ong.id],
        }
        for ong in ONG.query.filter(ONG.id != ong_id).order_by(ONG.nombre).all()
        if ong.id in usuario_por_ong
    ]


def _validar_convocatoria_y_duplicado(convocatoria_id, ong_id, oferta_excluir_id=None):
    convocatoria = (
        LoteNecesidades.query
        .filter_by(id=convocatoria_id)
        .with_for_update()
        .first()
    )
    if convocatoria is None:
        raise ValueError('La convocatoria seleccionada no existe.')

    query = (
        db.session.query(OfertaParticipante.id)
        .join(Oferta, Oferta.id == OfertaParticipante.oferta_id)
        .filter(
            Oferta.convocatoria_id == convocatoria_id,
            OfertaParticipante.ong_id == ong_id,
        )
    )
    if oferta_excluir_id is not None:
        query = query.filter(OfertaParticipante.oferta_id != oferta_excluir_id)
    if query.first():
        raise ValueError('Tu ONG ya tiene una oferta registrada para esta convocatoria.')
    return convocatoria


def _crear_participacion(oferta, ong_id, estado, notificar=False):
    participacion = OfertaParticipante.query.filter_by(
        oferta_id=oferta.id,
        ong_id=ong_id,
    ).first()
    if participacion is None:
        participacion = OfertaParticipante(
            oferta=oferta,
            ong_id=ong_id,
            estado=estado,
        )
        db.session.add(participacion)
        if notificar:
            _notificar_nuevas_ongs(oferta, {ong_id}, set())
    return participacion


def _validar_ong_notificable(ong_id):
    for usuario in Usuario.query.filter_by(rol=RolEnum.ONG).all():
        try:
            if int((usuario.datos_adicionales or {}).get('ong_id')) == ong_id:
                return
        except (TypeError, ValueError):
            continue
    raise ValueError('La ONG colaboradora no tiene un usuario asociado.')


def _notificar_nuevas_ongs(oferta, ong_ids, ong_ids_notificadas):
    nuevas = set(ong_ids) - set(ong_ids_notificadas)
    if not nuevas:
        return

    for usuario in Usuario.query.filter_by(rol=RolEnum.ONG).all():
        try:
            participante_id = int((usuario.datos_adicionales or {}).get('ong_id'))
        except (TypeError, ValueError):
            continue
        if participante_id not in nuevas:
            continue
        crear_notificacion(
            usuario_id=usuario.id,
            titulo=f'Participación en oferta #{oferta.id_oferta}',
            mensaje=f'Tu ONG fue incluida como participante en la oferta #{oferta.id_oferta}.',
            tipo=TipoNotificacionEnum.SISTEMA,
            referencia_id=oferta.id_oferta,
            commit=False,
        )


def convocatorias_postuladas(ong_id):
    filas = (
        db.session.query(Oferta.convocatoria_id)
        .join(VersionOferta, VersionOferta.id_oferta == Oferta.id)
        .join(DetalleVersionOferta, DetalleVersionOferta.id_version == VersionOferta.id)
        .filter(
            Oferta.convocatoria_id.isnot(None),
            VersionOferta.numero_version == Oferta.version_actual,
            DetalleVersionOferta.id_ong == ong_id,
            Oferta.estado != EstadoOfertaEnum.RECHAZADA,
        )
        .distinct()
        .all()
    )
    return {convocatoria_id for (convocatoria_id,) in filas}


def invitaciones_pendientes_por_convocatoria(ong_id):
    filas = (
        db.session.query(Oferta.convocatoria_id, Oferta.id)
        .join(OfertaParticipante, OfertaParticipante.oferta_id == Oferta.id)
        .filter(
            OfertaParticipante.ong_id == ong_id,
            OfertaParticipante.estado == 'Pendiente',
            Oferta.convocatoria_id.isnot(None),
        )
        .all()
    )
    return {convocatoria_id: oferta_id for convocatoria_id, oferta_id in filas}


def listar_ofertas(id_ong):
    """Devuelve todas las ofertas."""
    ofertas = Oferta.query.all()
    resultado = []

    for oferta in ofertas:
        version_actual = VersionOferta.query.filter_by(
            id_oferta=oferta.id_oferta,
            numero_version=oferta.version_actual
        ).first()

        if version_actual is None:
            continue

        participa_ong = any(detalle.id_ong == id_ong for detalle in version_actual.detalles)
        participa_ong = participa_ong or OfertaParticipante.query.filter_by(
            oferta_id=oferta.id_oferta,
            ong_id=id_ong,
        ).first() is not None
        if not participa_ong:
            continue

        emergencia = db.session.get(Emergencia, oferta.id_emergencia)
        ongs_participantes = []

        for detalle in version_actual.detalles:
            if detalle.ong not in ongs_participantes:
                ongs_participantes.append(detalle.ong)
        for participacion in oferta.participaciones:
            if participacion.ong not in ongs_participantes:
                ongs_participantes.append(participacion.ong)

        recursos = []
        for detalle in version_actual.detalles:
            recursos.append({
                'nombre': detalle.recurso.nombre,
                'cantidad': detalle.cantidad,
                'ong': detalle.ong.nombre,
                'ong_id': detalle.id_ong,
            })

        participacion_actual = next(
            (item for item in oferta.participaciones if item.ong_id == id_ong),
            None,
        )
        tiene_aporte = any(detalle.id_ong == id_ong for detalle in version_actual.detalles)
        estado_participacion = (
            'Postulado' if tiene_aporte
            else (participacion_actual.estado if participacion_actual else 'Participante')
        )

        resultado.append({
            "id": oferta.id_oferta,
            "id_oferta": oferta.id_oferta,
            "nombre_emergencia": (emergencia.descripcion if emergencia else "Emergencia no encontrada"),
            "version": oferta.version_actual,
            "es_conjunta": oferta.es_conjunta,
            "estado": oferta.estado,
            "estado_participacion": estado_participacion,
            "es_creadora": oferta.creada_por_ong_id == id_ong,
            "convocatoria_id": oferta.convocatoria_id,
            "ongs_participantes": ongs_participantes,
            "recursos": recursos
            }),

    return resultado

def _validar_recursos(recursos, id_ong):
    """
    Verifica que haya al menos un recurso, que no se repitan, cantidades válidas y que correspondan a la ONG.
    """

    if not recursos:
        raise ValueError("Debe seleccionar al menos un recurso.")

    ids_recursos = [r["id_recurso"] for r in recursos]

    if len(ids_recursos) != len(set(ids_recursos)):
        raise ValueError("No se puede repetir un recurso dentro de una oferta.")

    recursos_modelos = {}

    for recurso_data in recursos:

        recurso = InventarioONG.query.filter_by(
            id=recurso_data["id_recurso"],
            ong_id=id_ong
        ).first()

        if recurso is None:
            raise ValueError(
                f"El recurso {recurso_data['id_recurso']} no pertenece a la ONG."
            )

        cantidad = recurso_data["cantidad"]

        if cantidad <= 0:
            raise ValueError(
                f"La cantidad del recurso '{recurso.nombre}' debe ser mayor a 0."
            )

        if cantidad > recurso.cantidad_disponible:
            raise ValueError(
                f"No hay suficiente cantidad disponible de '{recurso.nombre}'. "
                f"Disponible: {recurso.cantidad_disponible}."
            )

        recursos_modelos[recurso.id] = recurso
    
    return recursos_modelos

def crear_oferta(convocatoria_id, recursos, ong_id, usuario_id, colaboradoras_ids=()):
    convocatoria = _validar_convocatoria_y_duplicado(convocatoria_id, ong_id)
    recursos_modelos = _validar_recursos(recursos, ong_id)
    try:
        colaboradoras_ids = {int(value) for value in colaboradoras_ids}
    except (TypeError, ValueError) as error:
        raise ValueError('La selección de ONGs colaboradoras no es válida.') from error
    if ong_id in colaboradoras_ids:
        raise ValueError('No puedes invitar a tu propia ONG.')
    for colaboradora_id in colaboradoras_ids:
        if ONG.query.filter_by(id=colaboradora_id).first() is None:
            raise ValueError('Una ONG colaboradora seleccionada no existe.')
        _validar_ong_notificable(colaboradora_id)
        _validar_convocatoria_y_duplicado(convocatoria_id, colaboradora_id)

    if not recursos:
        raise ValueError('Debe asignar al menos un recurso de tu inventario.')

    try:
        oferta = Oferta(
            id_emergencia=convocatoria.emergencia_id,
            convocatoria_id=convocatoria.id,
            creada_por_ong_id=ong_id,
            version_actual=1,
            fecha_ultima_modificacion=datetime.utcnow(),
            fecha_creacion=datetime.utcnow(),
        )
        db.session.add(oferta)
        db.session.flush()
        version = VersionOferta(
            id_oferta=oferta.id_oferta,
            numero_version=1,
            fecha_version=datetime.utcnow(),
            usuario_modificacion=usuario_id,
            estado_version=EstadoOfertaEnum.PENDIENTE.value,
        )
        db.session.add(version)
        db.session.flush()
        for recurso_data in recursos:
            inventario_item = recursos_modelos[recurso_data['id_recurso']]
            db.session.add(DetalleVersionOferta(
                id_version=version.id_version,
                id_ong=ong_id,
                id_recurso=inventario_item.id_recurso,
                cantidad=recurso_data['cantidad'],
                cantidad_adjudicada=0,
            ))
        _crear_participacion(oferta, ong_id, 'Aceptada')
        for colaboradora_id in colaboradoras_ids:
            _crear_participacion(oferta, colaboradora_id, 'Pendiente', notificar=True)
        oferta.es_conjunta = len(colaboradoras_ids) > 0
        db.session.commit()
        return oferta
    except Exception:
        db.session.rollback()
        raise


def obtener_oferta_para_modificar(id_oferta, id_ong):
    oferta = db.session.get(Oferta, id_oferta)
    if oferta is None:
        raise ValueError("La oferta no existe.")
    version = VersionOferta.query.filter_by(
        id_oferta=oferta.id_oferta,
        numero_version=oferta.version_actual
    ).first()
    if version is None:
        raise ValueError("La oferta no tiene una versión actual válida.")
    participacion = OfertaParticipante.query.filter_by(
        oferta_id=oferta.id,
        ong_id=id_ong,
    ).first()
    if not participacion and oferta.creada_por_ong_id != id_ong:
        raise ValueError('Tu ONG no participa en esta oferta.')
    return oferta, version, participacion


def modificar_oferta(id_oferta, recursos, ong_id, usuario_id, colaboradoras_ids=()):
    oferta, version_actual, participacion = obtener_oferta_para_modificar(id_oferta, ong_id)
    if oferta.convocatoria_id is not None:
        _validar_convocatoria_y_duplicado(
            oferta.convocatoria_id,
            ong_id,
            oferta_excluir_id=oferta.id,
        )
    if not recursos:
        raise ValueError('Debe asignar al menos un recurso de tu inventario.')

    recursos_modelos = _validar_recursos(recursos, ong_id)
    es_creadora = oferta.creada_por_ong_id == ong_id
    if not es_creadora and colaboradoras_ids:
        raise ValueError('Solo la ONG creadora puede invitar nuevas colaboradoras.')
    colaboradoras_nuevas = set()
    if es_creadora:
        try:
            colaboradoras_nuevas = {int(value) for value in colaboradoras_ids}
        except (TypeError, ValueError) as error:
            raise ValueError('La selección de ONGs colaboradoras no es válida.') from error
        colaboradoras_nuevas.discard(ong_id)
        for colaboradora_id in colaboradoras_nuevas:
            if ONG.query.filter_by(id=colaboradora_id).first() is None:
                raise ValueError('Una ONG colaboradora seleccionada no existe.')
            _validar_ong_notificable(colaboradora_id)
            _validar_convocatoria_y_duplicado(
                oferta.convocatoria_id,
                colaboradora_id,
                oferta_excluir_id=oferta.id,
            )

    detalles_propios = [detalle for detalle in version_actual.detalles if detalle.id_ong == ong_id]
    detalles_previos = {detalle.id_recurso: detalle for detalle in detalles_propios}
    for recurso_data in recursos:
        recurso = recursos_modelos[recurso_data['id_recurso']]
        cantidad_disponible = recurso.cantidad_disponible
        detalle_previo = detalles_previos.get(recurso.id_recurso)
        if detalle_previo:
            cantidad_disponible += detalle_previo.cantidad
        if recurso_data['cantidad'] > cantidad_disponible:
            raise ValueError(f"No hay suficiente cantidad disponible de '{recurso.nombre}'. Disponible: {cantidad_disponible}.")

    try:
        nuevo_num_version = oferta.version_actual + 1
        nueva_version = VersionOferta(
            id_oferta=oferta.id_oferta,
            numero_version=nuevo_num_version,
            fecha_version=datetime.utcnow(),
            usuario_modificacion=usuario_id,
            estado_version=EstadoOfertaEnum.PENDIENTE.value
        )
        db.session.add(nueva_version)
        db.session.flush()
        for detalle in version_actual.detalles:
            if detalle.id_ong != ong_id:
                db.session.add(DetalleVersionOferta(
                    id_version=nueva_version.id,
                    id_ong=detalle.id_ong,
                    id_recurso=detalle.id_recurso,
                    cantidad=detalle.cantidad,
                    cantidad_adjudicada=detalle.cantidad_adjudicada,
                ))
        for recurso_data in recursos:
            inventario_item = recursos_modelos[recurso_data['id_recurso']]
            db.session.add(DetalleVersionOferta(
                id_version=nueva_version.id,
                id_ong=ong_id,
                id_recurso=inventario_item.id_recurso,
                cantidad=recurso_data['cantidad'],
                cantidad_adjudicada=0,
            ))
        if participacion:
            participacion.estado = 'Aceptada'
        for colaboradora_id in colaboradoras_nuevas:
            _crear_participacion(oferta, colaboradora_id, 'Pendiente', notificar=True)
        oferta.version_actual = nuevo_num_version
        oferta.fecha_ultima_modificacion = datetime.utcnow()
        oferta.es_conjunta = OfertaParticipante.query.filter_by(oferta_id=oferta.id).count() > 1

        db.session.commit()
        return oferta

    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Error al crear la nueva versión de la oferta: {str(e)}")