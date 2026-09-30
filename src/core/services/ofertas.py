
from datetime import datetime

from src.core.database import db

from src.core.models.oferta import Oferta
from src.core.models.version_oferta import VersionOferta
from src.core.models.detalle_version_oferta import DetalleVersionOferta
from src.core.models.inventario import InventarioONG


def crear_oferta(id_emergencia, es_conjunta, recursos, id_ong):
    """
    Crea una nueva oferta junto con su primera versión
    y los detalles de los recursos ofrecidos.
    """

    if not id_emergencia:
        raise ValueError("Debe seleccionar una emergencia.")

    if not recursos:
        raise ValueError("Debe seleccionar al menos un recurso.")

    # Chequea que no repita recursos
    ids_recursos = [r["id_recurso"] for r in recursos]

    if len(ids_recursos) != len(set(ids_recursos)):
        raise ValueError("No se puede repetir un recurso dentro de una oferta.")

    # Verificar recursos y cantidades
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

    # Creo la oferta
    oferta = Oferta(
        id_emergencia=id_emergencia,
        es_conjunta=es_conjunta,
        fecha_creacion=datetime.utcnow(),
        fecha_ultima_modificacion=datetime.utcnow(),
        version_actual=1
    )

    db.session.add(oferta)
    db.session.flush()

    # Crear la primera versión
    version = VersionOferta(
        id_oferta=oferta.id_oferta,
        numero_version=1,
        fecha_version=datetime.utcnow(),
        usuario_modificacion=id_ong,
        estado_version="pendiente"
    )

    db.session.add(version)
    db.session.flush()

    # Crear los detalles
    for recurso_data in recursos:

        detalle = DetalleVersionOferta(
            id_version=version.id_version,
            id_ong=id_ong,
            id_recurso=recurso_data["id_recurso"],
            cantidad=recurso_data["cantidad"],
            cantidad_adjudicada=0
        )

        db.session.add(detalle)

    db.session.commit()

    return oferta


def obtener_oferta_para_modificar(id_oferta, id_ong):
    """
    Obtiene una oferta perteneciente a la ONG junto con su
    versión actual.
    """

    oferta = Oferta.query.get(id_oferta)

    if oferta is None:
        raise ValueError("La oferta no existe.")

    # Buscar la versión actual
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


def modificar_oferta(
    id_oferta,
    es_conjunta,
    recursos,
    id_ong
):
    """
    Modifica una oferta y crea una nueva versión de la misma
    """

    oferta, version_actual = obtener_oferta_para_modificar(
        id_oferta,
        id_ong
    )

    if not recursos:
        raise ValueError("Debe seleccionar al menos un recurso.")

    # Verificar recursos repetidos
    ids_recursos = [r["id_recurso"] for r in recursos]

    if len(ids_recursos) != len(set(ids_recursos)):
        raise ValueError("No se puede repetir un recurso dentro de una oferta.")

    # Verificar recursos y cantidades
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

        # Buscar si este recurso ya estaba en la versión anterior
        detalle_anterior = next(
            (
                detalle
                for detalle in version_actual.detalles
                if detalle.id_recurso == recurso.id
            ),
            None
        )

        cantidad_disponible_real = recurso.cantidad_disponible

        # Si el recurso ya estaba ofrecido en la versión anterior,
        # se puede volver a utilizar esa cantidad.
        if detalle_anterior is not None:
            cantidad_disponible_real += detalle_anterior.cantidad

        if cantidad > cantidad_disponible_real:
            raise ValueError(
                f"No hay suficiente cantidad disponible de '{recurso.nombre}'. "
                f"Disponible para esta modificación: "
                f"{cantidad_disponible_real}."
            )

    # Crear nueva versión
    nuevo_numero_version = oferta.version_actual + 1

    nueva_version = VersionOferta(
        id_oferta=oferta.id_oferta,
        numero_version=nuevo_numero_version,
        fecha_version=datetime.utcnow(),
        usuario_modificacion=id_ong,
        estado_version="pendiente"
    )

    db.session.add(nueva_version)
    db.session.flush()

    # Crear detalles de la nueva versión
    for recurso_data in recursos:

        detalle = DetalleVersionOferta(
            id_version=nueva_version.id_version,
            id_ong=id_ong,
            id_recurso=recurso_data["id_recurso"],
            cantidad=recurso_data["cantidad"],
            cantidad_adjudicada=0
        )

        db.session.add(detalle)

    # Actualizar la oferta
    oferta.version_actual = nuevo_numero_version
    oferta.es_conjunta = es_conjunta
    oferta.fecha_ultima_modificacion = datetime.utcnow()

    db.session.commit()

    return oferta