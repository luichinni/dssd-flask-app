from src.core.database import db
from src.core.models.inventario import InventarioONG
from src.core.models.recurso_catalogo import RecursoCatalogo
from src.core.models.detalle_version_oferta import DetalleVersionOferta
from src.core.models.version_oferta import VersionOferta
from src.core.models.oferta import Oferta
from src.core.enums import EstadoOfertaEnum
from sqlalchemy import func

def listar_inventario(ong_id: int, recurso_ids=None):
    """Devuelve inventario propio, opcionalmente limitado a recursos solicitados."""
    query = InventarioONG.query.filter_by(ong_id=ong_id)
    if recurso_ids is not None:
        recurso_ids = set(recurso_ids)
        if not recurso_ids:
            return []
        query = query.filter(InventarioONG.id_recurso.in_(recurso_ids))
    return query.order_by(InventarioONG.created_at.desc()).all()

def obtener_recurso(recurso_id: int, ong_id: int):
    """Obtiene un recurso garantizando que pertenezca a la ONG especificada."""
    return InventarioONG.query.filter_by(id=recurso_id, ong_id=ong_id).first()


def listar_catalogo_disponible(ong_id: int):
    return (
        RecursoCatalogo.query
        .filter(~RecursoCatalogo.inventarios.any(InventarioONG.ong_id == ong_id))
        .order_by(RecursoCatalogo.nombre.asc())
        .all()
    )


def cantidad_comprometida(ong_id: int, recurso_id: int, excluir_oferta_id: int = None) -> int:
    query = (
        db.session.query(func.coalesce(func.sum(DetalleVersionOferta.cantidad), 0))
        .join(VersionOferta, VersionOferta.id == DetalleVersionOferta.id_version)
        .join(Oferta, Oferta.id == VersionOferta.id_oferta)
        .filter(
            DetalleVersionOferta.id_ong == ong_id,
            DetalleVersionOferta.id_recurso == recurso_id,
            VersionOferta.numero_version == Oferta.version_actual,
            Oferta.estado.in_([
                EstadoOfertaEnum.PENDIENTE,
                EstadoOfertaEnum.ACEPTADA,
                EstadoOfertaEnum.ADJUDICADA,
            ]),
        )
    )
    if excluir_oferta_id is not None:
        query = query.filter(Oferta.id != excluir_oferta_id)
    cantidad = query.scalar()
    return int(cantidad or 0)


def sincronizar_disponible(item: InventarioONG) -> int:
    """Actualiza la columna cantidad_disponible según total menos comprometido."""
    comprometida = cantidad_comprometida(item.ong_id, item.id_recurso)
    item.cantidad_disponible = max(0, item.cantidad_total - comprometida)
    return item.cantidad_disponible



def crear_recurso(ong_id: int, data: dict):
    """Añade al inventario un recurso existente del catálogo."""
    try:
        catalogo_id = int(data['recurso_catalogo_id'])
        cantidad = int(data['cantidad_total'])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Selecciona un recurso del catálogo e indica una cantidad válida.') from error
    if cantidad < 0:
        raise ValueError('La cantidad debe ser mayor o igual a cero.')
    catalogo = db.session.get(RecursoCatalogo, catalogo_id)
    if catalogo is None:
        raise ValueError('El recurso seleccionado no existe en el catálogo.')
    if obtener_recurso_por_catalogo(ong_id, catalogo_id):
        raise ValueError('Ese recurso ya forma parte de tu inventario.')

    recurso = InventarioONG(
        ong_id=ong_id,
        recurso=catalogo,
        cantidad_total=cantidad,
        cantidad_disponible=cantidad,
    )
    db.session.add(recurso)
    db.session.commit()
    return recurso


def obtener_recurso_por_catalogo(ong_id: int, recurso_catalogo_id: int):
    return InventarioONG.query.filter_by(
        ong_id=ong_id,
        id_recurso=recurso_catalogo_id,
    ).first()


def actualizar_recurso(recurso_id: int, ong_id: int, data: dict):
    """Actualiza stock sin reducirlo por debajo de las cantidades comprometidas."""
    recurso = (
        InventarioONG.query
        .filter_by(id=recurso_id, ong_id=ong_id)
        .with_for_update()
        .first()
    )
    if not recurso:
        return None
    try:
        nueva_total = int(data['cantidad_total'])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('La cantidad debe ser un número entero válido.') from error
    if nueva_total < 0:
        raise ValueError('La cantidad debe ser mayor o igual a cero.')

    comprometida = cantidad_comprometida(ong_id, recurso.id_recurso)
    if nueva_total < comprometida:
        raise ValueError(f'La cantidad total no puede ser menor a las {comprometida} unidades comprometidas en ofertas activas.')

    recurso.cantidad_total = nueva_total
    recurso.cantidad_disponible = max(0, nueva_total - comprometida)

    db.session.commit()
    return recurso


def eliminar_recurso(recurso_id: int, ong_id: int) -> bool:
    """Elimina un recurso del inventario si no tiene stock comprometido."""
    recurso = (
        InventarioONG.query
        .filter_by(id=recurso_id, ong_id=ong_id)
        .with_for_update()
        .first()
    )
    if not recurso:
        return False
    comprometida = cantidad_comprometida(ong_id, recurso.id_recurso)
    if comprometida > 0:
        raise ValueError(
            f'No se puede eliminar el recurso "{recurso.nombre}" porque tiene {comprometida} unidades comprometidas en ofertas.'
        )
    db.session.delete(recurso)
    db.session.commit()
    return True
