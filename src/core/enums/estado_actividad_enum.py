from enum import Enum

class EstadoActividadEnum(str, Enum):
    EN_EJECUCION = "En Ejecución"
    FINALIZADA = "Finalizada"

    @classmethod
    def choices(cls):
        return [(estado.value, estado.value) for estado in cls]
