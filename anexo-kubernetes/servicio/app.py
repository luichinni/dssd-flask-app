import json
import unicodedata
from http import HTTPStatus


BASE_POR_GRAVEDAD = {1: 1, 2: 3, 3: 5, 4: 8}
AJUSTE_POR_ZONA = {"los hornos": 1, "tolosa": 1, "arroyo el gato": 2, "barrio ribereno": 2}


def calcular_prioridad(nivel_gravedad, zona_afectada):
    if type(nivel_gravedad) is not int or nivel_gravedad not in BASE_POR_GRAVEDAD:
        raise ValueError("El nivel de gravedad debe ser un entero entre 1 y 4.")
    if not isinstance(zona_afectada, str) or not zona_afectada.strip() or len(zona_afectada) > 100:
        raise ValueError("La zona afectada debe tener entre 1 y 100 caracteres.")

    texto = unicodedata.normalize("NFD", zona_afectada.casefold())
    sin_acentos = "".join(letra for letra in texto if not unicodedata.combining(letra))
    zona = " ".join(sin_acentos.split())
    return BASE_POR_GRAVEDAD[nivel_gravedad] + AJUSTE_POR_ZONA.get(zona, 0)


def application(environ, start_response):
    ruta = environ["PATH_INFO"]
    metodo = environ["REQUEST_METHOD"]
    if ruta == "/salud" and metodo == "GET":
        estado, datos = HTTPStatus.OK, {"estado": "ok"}
    elif ruta == "/prioridades" and metodo == "POST":
        estado, datos = solicitar_prioridad(environ)
    else:
        estado, datos = HTTPStatus.NOT_FOUND, {"error": "Ruta inexistente."}
    cuerpo = json.dumps(datos).encode("utf-8")
    start_response(f"{estado.value} {estado.phrase}", [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(cuerpo))),
    ])
    return [cuerpo]


def solicitar_prioridad(environ):
    try:
        longitud = int(environ.get("CONTENT_LENGTH") or 0)
        if not 0 < longitud <= 4096:
            raise ValueError()
        datos = json.loads(environ["wsgi.input"].read(longitud))
        if not isinstance(datos, dict):
            raise ValueError()
    except ValueError:
        return HTTPStatus.BAD_REQUEST, {"error": "Enviá un objeto JSON válido."}

    try:
        prioridad = calcular_prioridad(datos.get("nivel_gravedad"), datos.get("zona_afectada"))
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"error": str(error)}
    return HTTPStatus.OK, {"prioridad": prioridad}
