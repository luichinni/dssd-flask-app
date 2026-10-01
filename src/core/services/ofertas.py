from src.core.models import Oferta
from src.core.enums import EstadoOfertaEnum
from src.core.database import db

def crear_oferta():
    """Lleva a la pagina de creacion de ofertas."""
    pass

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