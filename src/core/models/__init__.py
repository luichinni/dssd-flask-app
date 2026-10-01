from .user import Usuario
from .inventario import InventarioONG
from .notificacion import Notificacion
from .actividad import ActividadONG
from .oferta import Oferta
from .oferta_participante import OfertaParticipante
from .version_oferta import VersionOferta
from .detalle_version_oferta import DetalleVersionOferta
from .municipio import Municipio
from .ong import ONG
from .recurso_catalogo import RecursoCatalogo
from .lote_necesidades import LoteNecesidades
from .lote_detalle import LoteDetalle
from .emergencia import Emergencia

OfertaVersion = VersionOferta
OfertaVersionDetalle = DetalleVersionOferta

__all__ = ["Usuario", "Municipio", "ONG", "RecursoCatalogo", "InventarioONG", "Emergencia", "LoteNecesidades", "LoteDetalle", "Oferta", "OfertaParticipante", "VersionOferta", "OfertaVersion", "DetalleVersionOferta", "OfertaVersionDetalle", "ActividadONG", "Notificacion"]
