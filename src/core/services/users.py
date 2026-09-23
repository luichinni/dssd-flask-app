from src.core.models import Usuario


def listar_usuarios():
    """Devuelve todos los usuarios ordenados por nombre."""
    return Usuario.query.order_by(Usuario.nombre.asc()).all()
