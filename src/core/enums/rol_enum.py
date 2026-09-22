from enum import Enum

class RolEnum(str, Enum):
    OPERADOR_MUNICIPAL = "Operador Municipal"
    CENTRO_COORDINADOR = "Centro Coordinador"
    ONG = "ONG"
    AUDITOR = "Auditor"

    @classmethod
    def choices(cls):
        """Retorna una lista de tuplas (valor, nombre) útil para formularios (WTForms)."""
        return [(role.value, role.value) for role in cls]