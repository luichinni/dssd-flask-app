"""Cliente REST de Bonita para iniciar procesos desde la aplicación."""
import json
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


class BonitaError(RuntimeError):
    """Error de configuración, conexión o respuesta de Bonita."""


def iniciar_proceso(datos_contrato=None, proceso_id=None):
    """Inicia una instancia y devuelve su caseId como int.

    Requiere contexto Flask. datos_contrato contiene las entradas exactas del
    contrato de instanciación de Bonita, no nombres arbitrarios de variables.
    No reintenta el POST: un timeout puede haber creado ya la instancia.
    """
    from flask import current_app

    config = current_app.config
    base_url = str(config.get("BONITA_URL") or "").rstrip("/")
    usuario = config.get("BONITA_USERNAME")
    password = config.get("BONITA_PASSWORD")
    proceso_id = proceso_id if proceso_id is not None else config.get("BONITA_PROCESS_ID")
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
        raise BonitaError("Configura BONITA_URL con la URL base, incluyendo /bonita.")
    if not usuario or not password:
        raise BonitaError("Configura BONITA_USERNAME y BONITA_PASSWORD.")
    try:
        if isinstance(proceso_id, bool):
            raise ValueError()
        proceso_id = int(str(proceso_id))
        timeout = float(config.get("BONITA_TIMEOUT", 15))
        if proceso_id <= 0 or not 0 < timeout < float("inf"):
            raise ValueError()
    except (TypeError, ValueError):
        raise BonitaError("BONITA_PROCESS_ID y BONITA_TIMEOUT deben ser positivos.") from None
    if datos_contrato is None:
        datos_contrato = {}
    if not isinstance(datos_contrato, dict):
        raise BonitaError("Los datos del contrato deben ser un diccionario.")
    try:
        payload = json.dumps(datos_contrato, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise BonitaError("Los datos del contrato deben ser serializables como JSON.") from None

    cookies = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))

    def enviar(request, etapa):
        try:
            with opener.open(request, timeout=timeout) as response:
                # Un redirect a la pantalla de login no acredita una operación.
                if response.geturl() != request.full_url:
                    raise BonitaError(f"Bonita redirigió la petición de {etapa}. Revisa la URL y autenticación.")
                return response.read()
        except HTTPError as error:
            status = error.code
            error.close()
            raise BonitaError(f"Bonita respondió HTTP {status} al {etapa}.") from None
        except (URLError, TimeoutError, OSError):
            detalle = (
                " El resultado es incierto; verifica los casos antes de reintentar."
                if etapa == "iniciar el proceso" else ""
            )
            raise BonitaError(f"No se pudo completar la conexión con Bonita al {etapa}.{detalle}") from None

    enviar(Request(
        f"{base_url}/loginservice",
        data=urlencode({"username": usuario, "password": password, "redirect": "false"}).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    ), "autenticar")
    token = next((cookie.value for cookie in cookies if cookie.name == "X-Bonita-API-Token"), None)
    if not token:
        raise BonitaError("Bonita no devolvió el token de sesión. Revisa las credenciales y la URL.")

    respuesta = enviar(Request(
        f"{base_url}/API/bpm/process/{proceso_id}/instantiation",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json", "X-Bonita-API-Token": token},
        method="POST",
    ), "iniciar el proceso")
    try:
        case_id = json.loads(respuesta)["caseId"]
        if isinstance(case_id, bool):
            raise ValueError()
        case_id = int(str(case_id))
        if case_id <= 0:
            raise ValueError()
        return case_id
    except (ValueError, TypeError, KeyError):
        raise BonitaError(
            "Bonita devolvió una respuesta sin caseId válido. Verifica los casos antes de reintentar."
        ) from None
