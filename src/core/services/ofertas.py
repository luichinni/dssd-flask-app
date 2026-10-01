from src.core.models import Oferta
from src.core.enums import EstadoOfertaEnum
from src.core.database import db
from datetime import datetime

from src.core.database import db
from src.core.models.oferta import Oferta
from src.core.models.version_oferta import VersionOferta
from src.core.models.detalle_version_oferta import DetalleVersionOferta
from src.core.models.inventario import InventarioONG
from src.core.enums import EstadoOfertaEnum
from src.core.models.emergencia import Emergencia

def guardar_oferta():
    """Guarda la oferta en la base de datos."""
    pass

def listar_ofertas_aceptadas(emergencia_id: int):
    """Devuelve las ofertas aceptadas de una emergencia, candidatas a ser adjudicadas."""
    return (
        Oferta.query
        .filter_by(id_emergencia=emergencia_id, estado=EstadoOfertaEnum.ACEPTADA.value)
        .order_by(Oferta.fecha_creacion.desc())
        .all()
    )

def obtener_version_vigente(oferta: Oferta):
    """Devuelve la versión vigente (actual) de una oferta, con sus recursos ofrecidos."""
    return next(
        (v for v in oferta.versiones if v.numero_version == oferta.version_actual),
        None,
    )


def adjudicar_oferta(oferta_id: int):
    """Marca una oferta como Adjudicada y adjudica la cantidad completa ofrecida en su versión vigente."""
    oferta = Oferta.query.get_or_404(oferta_id)

    if oferta.estado != EstadoOfertaEnum.ACEPTADA.value:
        raise ValueError(f"Solo se pueden adjudicar ofertas en estado Aceptada (estado actual: {oferta.estado})")

    oferta.estado = EstadoOfertaEnum.ADJUDICADA.value

    version_vigente = next(
        (v for v in oferta.versiones if v.numero_version == oferta.version_actual),
        None,
    )
    if version_vigente:
        for detalle in version_vigente.detalles:
            detalle.cantidad_adjudicada = detalle.cantidad  # adjudicación total, no parcial

    db.session.commit()
    return oferta
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
        if not participa_ong:
            continue

        emergencia = db.session.get(Emergencia, oferta.id_emergencia)
        ongs_participantes = []

        for detalle in version_actual.detalles:
            if detalle.ong not in ongs_participantes:
                ongs_participantes.append(detalle.ong)

        recursos = []

        for detalle in version_actual.detalles:
            if detalle.recurso not in recursos:
                recursos.append({
                    'nombre': detalle.recurso.nombre,
                    'cantidad': detalle.cantidad
                })

        resultado.append({
            "id": oferta.id_oferta,
            "id_oferta": oferta.id_oferta,
            "nombre_emergencia": (emergencia.descripcion if emergencia else "Emergencia no encontrada"),
            "version": oferta.version_actual,
            "es_conjunta": oferta.es_conjunta,
            "estado": oferta.estado,
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

def crear_oferta(id_emergencia, recursos, ong_id, usuario_id):
    """
    Crea una nueva oferta junto con su primera versión
    y los detalles de los recursos ofrecidos.
    """

    if not id_emergencia:
        raise ValueError("Debe seleccionar una emergencia.")

    if not recursos:
        raise ValueError("Debe seleccionar al menos un recurso.")

    recursos_modelos = _validar_recursos(recursos, ong_id)

    try: 
        oferta = Oferta(
            id_emergencia=id_emergencia,
            version_actual=1,
            fecha_ultima_modificacion=datetime.utcnow(),
            fecha_creacion=datetime.utcnow()
        )

        db.session.add(oferta)
        db.session.flush()

        version = VersionOferta(
            id_oferta=oferta.id_oferta,
            numero_version=1,
            fecha_version=datetime.utcnow(),
            usuario_modificacion=usuario_id,
            estado_version=EstadoOfertaEnum.PENDIENTE.value
        )

        db.session.add(version)
        db.session.flush()

        detalles_creados = []
        for recurso_data in recursos:
            detalle = DetalleVersionOferta(
                id_version=version.id_version,
                id_ong=ong_id,
                id_recurso=recursos_modelos[recurso_data["id_recurso"]].id_recurso,
                cantidad=recurso_data["cantidad"],
                cantidad_adjudicada=0
            )

            db.session.add(detalle)
            detalles_creados.append(detalle)

        ongs_participantes = {detalle.id_ong for detalle in detalles_creados}
        oferta.es_conjunta = len(ongs_participantes) > 1

        db.session.commit()
        return oferta
    except:
        db.session.rollback()
        raise


def obtener_oferta_para_modificar(id_oferta, id_ong):
    """
    Obtiene una oferta perteneciente a la ONG junto con su
    versión actual.
    """

    oferta = db.session.get(Oferta, id_oferta)

    if oferta is None:
        raise ValueError("La oferta no existe.")

    # se busca la versión actual
    version = VersionOferta.query.filter_by(
        id_oferta=oferta.id_oferta,
        numero_version=oferta.version_actual
    ).first()

    if version is None:
        raise ValueError("La oferta no tiene una versión actual válida.")

    # Verificar que la ONG sea propietaria de la oferta
    pertenece_ong = any(
        detalle.id_ong == id_ong
        for detalle in version.detalles
    )

    if not pertenece_ong:
        raise ValueError("La oferta no pertenece a esta ONG.")

    return oferta, version


def modificar_oferta(id_oferta, recursos, ong_id, usuario_id):
    """
    Modifica una oferta y crea una nueva versión de la misma, pero modifica sus propios recursos solamente
    """

    oferta, version_actual = obtener_oferta_para_modificar(
        id_oferta,
        ong_id
    )

    if not recursos:
        raise ValueError("Debe seleccionar al menos un recurso.")

    # Verificar recursos repetidos
    ids_recursos = [r["id_recurso"] for r in recursos]

    if len(ids_recursos) != len(set(ids_recursos)):
        raise ValueError("No se puede repetir un recurso dentro de una oferta.")

    detalles_ong_actual = [detalle for detalle in version_actual.detalles if detalle.id_ong == ong_id]
    detalles_previos = {detalle.id_recurso: detalle for detalle in detalles_ong_actual}
    recursos_modelos = {}

    for recurso_data in recursos:
        recurso = InventarioONG.query.filter_by(
            id=recurso_data["id_recurso"],
            ong_id=ong_id
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

        cant_disponible_real = recurso.cantidad_disponible
        detalle_previo = detalles_previos.get(recurso.id_recurso)

        if detalle_previo is not None:
            cant_disponible_real += detalle_previo.cantidad

        if cantidad > cant_disponible_real:
            raise ValueError(
                f"No hay suficiente cantidad disponible de '{recurso.nombre}'. "
                f"Disponible: {cant_disponible_real}."
            )
        recursos_modelos[recurso_data["id_recurso"]] = recurso
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

        detalles_creados = []
        for detalle_anterior in version_actual.detalles:
            if detalle_anterior.id_ong != ong_id:
                nuevo_detalle = DetalleVersionOferta(
                    id_version=nueva_version.id_version,
                    id_ong=detalle_anterior.id_ong,
                    id_recurso=detalle_anterior.id_recurso,
                    cantidad=detalle_anterior.cantidad,
                    cantidad_adjudicada=0
                    )
                db.session.add(nuevo_detalle)
                detalles_creados.append(nuevo_detalle)

        for recurso_data in recursos:
            nuevo_detalle = DetalleVersionOferta(
                id_version=nueva_version.id_version,
                id_ong=ong_id,
                id_recurso=recursos_modelos[recurso_data["id_recurso"]].id_recurso,
                cantidad=recurso_data["cantidad"],
                cantidad_adjudicada=0
            )
            db.session.add(nuevo_detalle)
            detalles_creados.append(nuevo_detalle)

        oferta.version_actual = nuevo_num_version
        oferta.fecha_ultima_modificacion = datetime.utcnow()
        ongs_participantes = {detalle.id_ong for detalle in detalles_creados}
        oferta.es_conjunta = len(ongs_participantes) > 1

        db.session.commit()
        return oferta

    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Error al crear la nueva versión de la oferta: {str(e)}")
