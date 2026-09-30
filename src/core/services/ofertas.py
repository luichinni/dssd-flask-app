from src.core.models import (
    Oferta,
    VersionOferta,
    DetalleVersionOferta,
    InventarioONG
)
from src.core.enums import EstadoOfertaEnum
from src.core.database import db

def listar_ofertas():
    return Oferta.query.all()

def obtener_oferta(id_oferta):
    return Oferta.query.get(id_oferta)

def crear_oferta(ong, nombre, descripcion, emergencia, detalles):
    """Crea una nueva oferta en la base de datos."""
    oferta = Oferta(
        ong=ong,
        nombre=nombre,
        descripcion=descripcion,
        emergencia=emergencia,
        detalles=detalles
    )

    db.session.add(oferta)
    db.session.flush()

    