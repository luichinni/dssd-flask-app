"""Cliente REST para iniciar casos y completar tareas de Bonita."""
import json
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from datetime import datetime
from src.core.enums.accion_post_convocatoria import AccionPostOfertaEnum
class BonitaError(RuntimeError):
    """Error de configuración, conexión o respuesta de Bonita."""


def _id(value, nombre):
    try:
        if isinstance(value, bool):
            raise ValueError()
        result = int(str(value))
        if result <= 0:
            raise ValueError()
        return result
    except (TypeError, ValueError):
        raise BonitaError(f"{nombre} debe ser un entero positivo.") from None


class _ClienteBonita:
    def __init__(self):
        from flask import current_app

        config = current_app.config
        self.base_url = str(config.get("BONITA_URL") or "").rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
            raise BonitaError("Configura BONITA_URL con la URL base, incluyendo /bonita.")
        usuario, password = config.get("BONITA_USERNAME"), config.get("BONITA_PASSWORD")
        if not usuario or not password:
            raise BonitaError("Configura BONITA_USERNAME y BONITA_PASSWORD.")
        try:
            self.timeout = float(config.get("BONITA_TIMEOUT", 15))
            if not 0 < self.timeout < float("inf"):
                raise ValueError()
        except (TypeError, ValueError):
            raise BonitaError("BONITA_TIMEOUT debe ser positivo.") from None
        cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(cookies))
        self.token = None
        self._enviar(
            "/loginservice", "POST",
            urlencode({"username": usuario, "password": password, "redirect": "false"}).encode(),
            "application/x-www-form-urlencoded", "autenticar",
        )
        self.token = next((c.value for c in cookies if c.name == "X-Bonita-API-Token"), None)
        if not self.token:
            raise BonitaError("Bonita no devolvió el token de sesión. Revisa las credenciales y la URL.")

    def _enviar(self, path, method, data, content_type, etapa):
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if self.token:
            headers["X-Bonita-API-Token"] = self.token
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.geturl() != request.full_url:
                    raise BonitaError(f"Bonita redirigió la petición de {etapa}. Revisa la URL y autenticación.")
                return response.read()
        except HTTPError as error:
            status = error.code
            error.close()
            raise BonitaError(f"Bonita respondió HTTP {status} al {etapa}.") from None
        except (URLError, TimeoutError, OSError):
            detalle = " Verifica el caso antes de reintentar." if method != "GET" else ""
            raise BonitaError(f"No se pudo completar la conexión con Bonita al {etapa}.{detalle}") from None

    def pedir(self, path, method="GET", datos=None, etapa="consultar"):
        payload = None
        if datos is not None:
            try:
                payload = json.dumps(datos, allow_nan=False).encode("utf-8")
            except (TypeError, ValueError):
                raise BonitaError("Los datos deben ser serializables como JSON.") from None
        response = self._enviar(path, method, payload, "application/json" if payload is not None else None, etapa)
        if not response:
            return None
        try:
            return json.loads(response)
        except (ValueError, TypeError):
            raise BonitaError(f"Bonita devolvió JSON inválido al {etapa}. Verifica el caso antes de reintentar.") from None

    def tareas(self, case_id, archivadas=False):
        resource = "archivedHumanTask" if archivadas else "humanTask"
        result = []
        page = 0
        while True:
            query = urlencode({"c": 100, "p": page, "f": f"caseId={case_id}"})
            batch = self.pedir(f"/API/bpm/{resource}?{query}")
            if not isinstance(batch, list):
                raise BonitaError("Bonita no devolvió una lista de tareas válida.")
            # Defensa adicional para no actuar sobre tareas de otro caso.
            result.extend(t for t in batch if str(t.get("caseId")) == str(case_id))
            if len(batch) < 100:
                return result
            page += 1

    def completar(self, case_id, nombre, datos=None):
        """Consulta hasta que la tarea esté lista; nunca reintenta ejecución."""
        deadline = time.monotonic() + self.timeout
        while True:
            tasks = self.tareas(case_id)
            matches = [t for t in tasks if t.get("name") == nombre and t.get("state") == "ready"]
            if len(matches) > 1:
                raise BonitaError(f"Hay más de una tarea {nombre} disponible en el caso {case_id}.")
            if matches:
                task = matches[0]
                break
            if any(t.get("name") == nombre and t.get("state") == "completed" for t in self.tareas(case_id, True)):
                return  # Ya completada, no ejecutar de nuevo.
            if time.monotonic() >= deadline:
                raise BonitaError(f"La tarea {nombre} no está disponible en el caso {case_id}.")
            time.sleep(0.25)

        task_id = _id(task["id"], "ID de tarea")
        session = self.pedir("/API/system/session/unusedId")
        user_id = _id(session["user_id"], "ID de usuario")
        assigned = str(task.get("assigned_id") or "0")
        if assigned not in ("0", str(user_id)):
            raise BonitaError(f"La tarea {nombre} ya está asignada a otro usuario.")
        if assigned == "0":
            self.pedir(f"/API/bpm/humanTask/{task_id}", "PUT", {"assigned_id": user_id}, f"asignar {nombre}")
        self.pedir(f"/API/bpm/userTask/{task_id}/execution", "POST", datos or {}, f"completar {nombre}")


def iniciar_proceso(datos_contrato=None, proceso_id=None):
    """Inicia un caso y devuelve su ID; recibe entradas del contrato real.

    Requiere contexto Flask. No reintenta el POST: un timeout puede haber
    creado la instancia.
    """
    from flask import current_app

    process_id = _id(proceso_id if proceso_id is not None else current_app.config.get("BONITA_PROCESS_ID"), "BONITA_PROCESS_ID")
    datos = {} if datos_contrato is None else datos_contrato
    if not isinstance(datos, dict):
        raise BonitaError("Los datos del contrato deben ser un diccionario.")
    respuesta = _ClienteBonita().pedir(
        f"/API/bpm/process/{process_id}/instantiation", "POST", datos, "iniciar el proceso",
    )
    if not isinstance(respuesta, dict) or "caseId" not in respuesta:
        raise BonitaError("Bonita devolvió una respuesta sin caseId. Verifica los casos antes de reintentar.")
    return _id(respuesta["caseId"], "caseId")


def _iso_datetime(fecha: datetime, nombre: str) -> str:
    """Convierte un datetime con timezone al formato que espera un contrato
    DATE-TIME (TIME ZONE) de Bonita (ISO 8601, milisegundos, con offset)."""
    if fecha.tzinfo is None:
        raise BonitaError(f"{nombre} debe tener timezone (usa _utc() antes de llamar).")
    return fecha.isoformat(timespec="milliseconds")


def completar_publicacion_lote(case_id, emergencia_id, fecha_cierre_ofertas):
    """Avanza el caso en orden hasta completar Cargar ofertas de ayuda.

    Registrar emergencia es un prerrequisito: su información ya está guardada
    en la app. Se omiten tareas archivadas como completed. Los POST de
    ejecución no se reintentan automáticamente.
    """
    case_id = _id(case_id, "ID del caso")
    emergencia_id = _id(emergencia_id, "ID de emergencia")
    fecha_cierre_iso = _iso_datetime(fecha_cierre_ofertas, "fecha_cierre_ofertas")

    cliente = _ClienteBonita()
    cliente.completar(case_id, "Registrar emergencia", {"id_emergencia_input": emergencia_id})
    cliente.completar(case_id, "Crear lotes de necesidades")
    cliente.completar(case_id, "Publicar convocatoria", {"fecha_cierre_input": fecha_cierre_iso})
    #cliente.completar(case_id, "Cargar ofertas de ayuda", {"fecha_cierre_input": fecha_cierre_iso})


def completar_decision_post_convocatoria(case_id, decision: AccionPostOfertaEnum, nueva_fecha_cierre=None):
    """
    Avanza el flujo post-evaluación según la decisión del coordinador.
    Si es REABRIR o REFORMULAR, completa el bucle hasta dejar la convocatoria
    publicada nuevamente con su nueva fecha de cierre.
    """
    case_id = _id(case_id, "ID del caso")
    if not isinstance(decision, AccionPostOfertaEnum):
        raise BonitaError(f"decision debe ser un AccionPostOfertaEnum, recibido: {decision!r}")

    cliente = _ClienteBonita()
    
    # 1. Completar la decisión en la tarea actual
    cliente.completar(case_id, "Evaluar y decidir curso de acción", {
        "accionPostOferta_input": decision.value
    })

    # 2. Si continúa, no hay más tareas en este tramo
    if decision == AccionPostOfertaEnum.CONTINUAR:
        return

    # 3. Si reabre o reformula, se requiere la nueva fecha de cierre
    if nueva_fecha_cierre is None:
        raise BonitaError("Se requiere una nueva fecha de cierre para reabrir o reformular la convocatoria.")

    fecha_cierre_iso = _iso_datetime(nueva_fecha_cierre, "nueva_fecha_cierre")

    # Espera a que el motor de Bonita procese la compuerta y cree la siguiente tarea
    time.sleep(1.5)

    if decision == AccionPostOfertaEnum.REFORMULAR:
        # Pasa por la tarea intermedia de reformulación
        cliente.completar(case_id, "Reformular lotes de necesidades")
        time.sleep(1.0)

    # Ambas ramas terminan en Publicar convocatoria para fijar el temporizador
    cliente.completar(case_id, "Publicar convocatoria", {
        "fecha_cierre_input": fecha_cierre_iso
    })