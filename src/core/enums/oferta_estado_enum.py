from enum import Enum

class EstadoOfertaEnum(str, Enum):
    PENDIENTE = "Pendiente"
    ACEPTADA = "Aceptada"
    RECHAZADA = "Rechazada"
    ADJUDICADA = "Adjudicada"

    @classmethod
    def choices(cls):
        return [(estado.value, estado.value) for estado in cls]