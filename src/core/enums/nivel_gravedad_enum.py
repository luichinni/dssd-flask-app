from enum import Enum
#decidi dejarlo como int para poder hacer comparaciones de gravedad mas facilmente
class nivel_gravedad_enum(int, Enum):
    BAJO = 1
    MEDIO = 2
    ALTO = 3
    CRITICO = 4