from src.core.database import db
from src.core.models.inventario import InventarioONG
from src.core.models.recurso_catalogo import RecursoCatalogo
from src.core.enums.tipo_recurso_enum import TipoRecursoEnum

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

def crear_recurso(ong_id: int, data: dict):
    """Crea un nuevo ítem en el inventario de la ONG."""
    nombre = data.get('nombre', '').strip()
    tipo_str = data.get('tipo_recurso', '')
    unidad = data.get('unidad_medida', 'Unidades').strip()
    cantidad = int(data.get('cantidad_total', 0))
    descripcion = data.get('descripcion', '').strip()

    # Normalizar enum
    tipo_enum = None
    for item in TipoRecursoEnum:
        if item.value == tipo_str or item.name == tipo_str:
            tipo_enum = item
            break
    if not tipo_enum:
        tipo_enum = TipoRecursoEnum.INSUMO

    catalogo = RecursoCatalogo(
        nombre=nombre,
        tipo_recursos=tipo_enum,
        unidad_medida=unidad,
        descripcion=descripcion or None,
    )
    recurso = InventarioONG(
        ong_id=ong_id,
        recurso=catalogo,
        cantidad_total=cantidad,
        cantidad_disponible=cantidad,
    )
    db.session.add(recurso)
    db.session.commit()
    return recurso

def actualizar_recurso(recurso_id: int, ong_id: int, data: dict):
    """Actualiza datos de un recurso propio de la ONG."""
    recurso = obtener_recurso(recurso_id, ong_id)
    if not recurso:
        return None

    recurso.recurso.nombre = data.get('nombre', recurso.nombre).strip()
    tipo_str = data.get('tipo_recurso')
    if tipo_str:
        for item in TipoRecursoEnum:
            if item.value == tipo_str or item.name == tipo_str:
                recurso.recurso.tipo_recursos = item
                break

    recurso.recurso.unidad_medida = data.get('unidad_medida', recurso.unidad_medida).strip()
    if 'cantidad_total' in data:
        nueva_total = int(data['cantidad_total'])
        diferencia = nueva_total - recurso.cantidad_total
        recurso.cantidad_total = nueva_total
        # Ajustar cantidad disponible manteniendo consistencia
        recurso.cantidad_disponible = max(0, recurso.cantidad_disponible + diferencia)

    if 'descripcion' in data:
        recurso.recurso.descripcion = data['descripcion'].strip() or None

    db.session.commit()
    return recurso

def eliminar_recurso(recurso_id: int, ong_id: int) -> bool:
    """Elimina un recurso del inventario."""
    recurso = obtener_recurso(recurso_id, ong_id)
    if not recurso:
        return False
    db.session.delete(recurso)
    db.session.commit()
    return True
