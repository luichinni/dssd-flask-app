from enum import Enum

class TipoNotificacionEnum(str, Enum):
    ADJUDICACION_LOTE = "Adjudicación de Lote"
    CONVOCATORIA = "Convocatoria"
    SISTEMA = "Sistema"

    @classmethod
    def choices(cls):
        return [(tipo.value, tipo.value) for tipo in cls]
