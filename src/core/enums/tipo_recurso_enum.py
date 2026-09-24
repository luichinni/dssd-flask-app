from enum import Enum

class TipoRecursoEnum(str, Enum):
    PERSONAL = "Personal"
    INSUMO = "Insumo"
    VEHICULO = "Vehículo"
    EQUIPAMIENTO = "Equipamiento"

    @classmethod
    def choices(cls):
        return [(tipo.value, tipo.value) for tipo in cls]
