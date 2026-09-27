from enum import Enum

class tipo_desastre_enum(str, Enum):
    #estos son los tipos de desastres naturales 
    geologico = "Geológico"
    meteorologico = "Meteorológico"
    hidrologico = "Hidrológico"
    biologico = "Biológico"
    #este tipo de desastre es causado por el hombre
    antropico = "Antropogénico"

