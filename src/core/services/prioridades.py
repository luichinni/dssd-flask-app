import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from flask import current_app


class PrioridadesError(RuntimeError):
    """La consulta al servicio de prioridades no pudo confirmarse."""


def obtener_prioridad(nivel_gravedad: int, zona_afectada: str) -> int:
    url = current_app.config["PRIORIDADES_URL"].rstrip("/")
    datos = json.dumps({"nivel_gravedad": nivel_gravedad, "zona_afectada": zona_afectada})
    try:
        solicitud = Request(
            f"{url}/prioridades",
            data=datos.encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urlopen(solicitud, timeout=3) as respuesta:
            resultado = json.loads(respuesta.read(4096))
    except (URLError, OSError, ValueError) as error:
        raise PrioridadesError("No se pudo consultar el servicio de prioridades.") from error

    prioridad = resultado.get("prioridad") if isinstance(resultado, dict) else None
    if type(prioridad) is not int or not 1 <= prioridad <= 10:
        raise PrioridadesError("El servicio de prioridades devolvió un resultado inválido.")
    return prioridad
