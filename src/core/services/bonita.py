"""Cliente REST para iniciar casos y completar tareas de Bonita."""
import json
import logging
import os
import threading
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from datetime import datetime
from src.core.enums.accion_post_convocatoria import AccionPostOfertaEnum
class BonitaError(RuntimeError):
    """Error de configuración, conexión o respuesta de Bonita."""

    def __init__(self, mensaje, status_code=None):
        super().__init__(mensaje)
        self.status_code = status_code


logger = logging.getLogger(__name__)
PROCESS_NAME = "BestRescueSyncEver"
PROCESS_VERSION = "1.0"


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
    def __init__(self, actor=None):
        from flask import current_app

        config = current_app.config
        self.base_url = str(config.get("BONITA_URL") or "").rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
            raise BonitaError("Configura BONITA_URL con la URL base, incluyendo /bonita.")
        prefijo = f"BONITA_{actor}" if actor else "BONITA"
        clave_usuario = f"{prefijo}_USERNAME"
        clave_password = f"{prefijo}_PASSWORD"
        usuario, password = config.get(clave_usuario), config.get(clave_password)
        if not usuario or not password:
            raise BonitaError(f"Configura {clave_usuario} y {clave_password}.")
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
            raise BonitaError(f"Bonita respondió HTTP {status} al {etapa}.", status_code=status) from None
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

    def resolver_process_definition_id(self):
        """Devuelve el ID de la única definición habilitada con nombre y versión exactos."""
        filtros = [
            f"name={PROCESS_NAME}",
            f"version={PROCESS_VERSION}",
            "activationState=ENABLED",
        ]
        query = urlencode([("p", 0), ("c", 100), *(("f", filtro) for filtro in filtros)])
        definiciones = self.pedir(f"/API/bpm/process?{query}", etapa="buscar la definición del proceso")
        if not isinstance(definiciones, list):
            raise BonitaError("Bonita no devolvió una lista de definiciones válida.")

        habilitadas = [
            proceso for proceso in definiciones
            if isinstance(proceso, dict)
            and proceso.get("name") == PROCESS_NAME
            and proceso.get("version") == PROCESS_VERSION
            and proceso.get("activationState") == "ENABLED"
        ]
        if not habilitadas:
            raise BonitaError(
                f"No se encontró habilitado el proceso {PROCESS_NAME} versión {PROCESS_VERSION}."
            )
        if len(habilitadas) != 1:
            raise BonitaError(
                f"Bonita devolvió varias definiciones habilitadas para {PROCESS_NAME} versión {PROCESS_VERSION}."
            )
        return _id(habilitadas[0].get("id"), "ID de definición de proceso")

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

    def listar_tareas_archivadas_caso(self, case_id):
        """Devuelve todas las tareas humanas archivadas de un caso."""
        case_id = _id(case_id, "ID del caso")
        return self.tareas(case_id, archivadas=True)

    def obtener_caso_archivado(self, case_id):
        """Devuelve el registro archivado de un caso (si ya finalizó) o None."""
        case_id = _id(case_id, "ID del caso")
        query = urlencode({"c": 1, "p": 0, "f": f"sourceObjectId={case_id}"})
        casos = self.pedir(f"/API/bpm/archivedCase?{query}", etapa="consultar caso archivado")
        if isinstance(casos, list) and casos:
            return casos[0]
        return None

    def obtener_caso_activo(self, case_id):
        """Devuelve el caso activo en Bonita o None si no existe/ya archivado."""
        case_id = _id(case_id, "ID del caso")
        try:
            return self.pedir(f"/API/bpm/case/{case_id}", etapa="consultar caso activo")
        except BonitaError as error:
            if error.status_code == 404:
                return None
            raise

    def completar(self, case_id, nombre, datos=None, esperar_nueva=False):
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
            if not esperar_nueva and any(t.get("name") == nombre and t.get("state") == "completed" for t in self.tareas(case_id, True)):
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


def resolver_process_definition_id():
    """Busca y almacena el ID dinámico de BestRescueSyncEver 1.0."""
    from flask import current_app

    process_id = _ClienteBonita().resolver_process_definition_id()
    current_app.config["BONITA_PROCESS_ID"] = process_id
    return process_id


def iniciar_proceso(datos_contrato=None, proceso_id=None):
    """Inicia un caso y devuelve su ID; recibe entradas del contrato real.

    Para BestRescueSyncEver 1.0 resuelve el ID dinámicamente. Solo reintenta el
    POST si Bonita devuelve HTTP 404 para una definición que quedó obsoleta;
    nunca reintenta ante timeout, error 5xx o respuesta ambigua.
    """
    from flask import current_app

    datos = {} if datos_contrato is None else datos_contrato
    if not isinstance(datos, dict):
        raise BonitaError("Los datos del contrato deben ser un diccionario.")

    cliente = _ClienteBonita()
    dinamico = proceso_id is None
    process_id = proceso_id
    if dinamico:
        process_id = current_app.config.get("BONITA_PROCESS_ID")
        if not process_id:
            process_id = cliente.resolver_process_definition_id()
            current_app.config["BONITA_PROCESS_ID"] = process_id
    process_id = _id(process_id, "ID de definición de proceso")

    try:
        respuesta = cliente.pedir(
            f"/API/bpm/process/{process_id}/instantiation", "POST", datos, "iniciar el proceso",
        )
    except BonitaError as error:
        # 404 es rechazo definitivo de esa definición. Errores de transporte,
        # 5xx y respuestas inválidas son ambiguos y jamás disparan otro POST.
        if not dinamico or error.status_code != 404:
            raise
        nuevo_id = cliente.resolver_process_definition_id()
        if nuevo_id == process_id:
            raise
        current_app.config["BONITA_PROCESS_ID"] = nuevo_id
        logger.info("La definición Bonita obsoleta se actualizó tras un redeploy.")
        respuesta = cliente.pedir(
            f"/API/bpm/process/{nuevo_id}/instantiation", "POST", datos, "reintentar el inicio del proceso",
        )

    if not isinstance(respuesta, dict) or "caseId" not in respuesta:
        raise BonitaError("Bonita devolvió una respuesta sin caseId. Verifica los casos antes de reintentar.")
    return _id(respuesta["caseId"], "caseId")


def _iso_datetime(fecha: datetime, nombre: str) -> str:
    """Convierte un datetime al formato que espera un contrato
    DATE-TIME (TIME ZONE) de Bonita (ISO 8601, milisegundos, en hora de Argentina)."""
    from src.core.timezone import a_argentina
    if fecha.tzinfo is None:
        raise BonitaError(f"{nombre} debe tener timezone (usa a_argentina() antes de llamar).")
    return a_argentina(fecha).isoformat(timespec="milliseconds")


def completar_publicacion_lote(case_id, emergencia_id, fecha_cierre_ofertas):
    """Avanza el caso en orden hasta publicar la convocatoria.

    Registrar emergencia es un prerrequisito: su información ya está guardada
    en la app. Se omiten tareas archivadas como completed. Los POST de
    ejecución no se reintentan automáticamente.
    """
    case_id = _id(case_id, "ID del caso")
    emergencia_id = _id(emergencia_id, "ID de emergencia")
    fecha_cierre_iso = _iso_datetime(fecha_cierre_ofertas, "fecha_cierre_ofertas")

    _ClienteBonita().completar(case_id, "Registrar emergencia", {"id_emergencia_input": emergencia_id})
    cliente = _ClienteBonita("CCR")
    cliente.completar(case_id, "Crear lotes de necesidades")
    cliente.completar(case_id, "Publicar convocatoria", {"fecha_cierre_input": fecha_cierre_iso})


def completar_decision_post_convocatoria(case_id, decision: AccionPostOfertaEnum, nueva_fecha_cierre=None):
    """
    Avanza el flujo post-evaluación según la decisión del coordinador.
    Si es REABRIR o REFORMULAR, completa el bucle hasta dejar la convocatoria
    publicada nuevamente con su nueva fecha de cierre.
    """
    case_id = _id(case_id, "ID del caso")
    if not isinstance(decision, AccionPostOfertaEnum):
        raise BonitaError(f"decision debe ser un AccionPostOfertaEnum, recibido: {decision!r}")

    if decision != AccionPostOfertaEnum.CONTINUAR:
        if nueva_fecha_cierre is None:
            raise BonitaError("Se requiere una nueva fecha de cierre para reabrir o reformular la convocatoria.")
        fecha_cierre_iso = _iso_datetime(nueva_fecha_cierre, "nueva_fecha_cierre")

    cliente = _ClienteBonita("CCR")
    cliente.completar(case_id, "Evaluar y decidir curso de acción", {
        "accionPostOferta_input": decision.value
    }, esperar_nueva=True)

    if decision == AccionPostOfertaEnum.CONTINUAR:
        return

    if decision == AccionPostOfertaEnum.REFORMULAR:
        cliente.completar(case_id, "Reformular lotes de necesidades", esperar_nueva=True)

    cliente.completar(case_id, "Publicar convocatoria", {
        "fecha_cierre_input": fecha_cierre_iso
    }, esperar_nueva=True)


def construir_solicitud_validacion(emergencia_id: int) -> dict:
    """Construye el payload de ofertas para validar en el servicio externo y marca lotes en validación."""
    from src.core.database import db
    from src.core.models.emergencia import Emergencia
    from src.core.models.lote_necesidades import LoteNecesidades
    from src.core.models.oferta import Oferta
    from src.core.enums import EstadoOfertaEnum
    from src.core.services.ofertas import detalles_para_convocatoria

    try:
        emergencia_id = _id(emergencia_id, "ID de emergencia")
    except BonitaError as exc:
        raise ValueError(str(exc)) from exc

    emergencia = db.session.get(Emergencia, emergencia_id)
    if not emergencia:
        raise ValueError(f"La emergencia {emergencia_id} no existe.")

    estado_rechazada = (
        EstadoOfertaEnum.RECHAZADA.value
        if hasattr(EstadoOfertaEnum.RECHAZADA, "value")
        else EstadoOfertaEnum.RECHAZADA
    )
    ofertas = (
        Oferta.query
        .filter(Oferta.id_emergencia == emergencia_id)
        .filter(Oferta.estado != estado_rechazada)
        .all()
    )

    tipo_desastre = (
        emergencia.tipo_desastre.name.lower()
        if hasattr(emergencia.tipo_desastre, "name")
        else str(emergencia.tipo_desastre).lower()
    )
    gravedad_map = {1: "bajo", 2: "medio", 3: "alto", 4: "critico"}
    gravedad = gravedad_map.get(emergencia.nivel_gravedad, "medio")

    ofertas_payload = []
    for of in ofertas:
        detalles = detalles_para_convocatoria(of)
        if not detalles:
            continue
        cant_por_recurso: dict[int, int] = {}
        for d in detalles:
            cant_por_recurso[d.id_recurso] = cant_por_recurso.get(d.id_recurso, 0) + int(d.cantidad)
        ofertas_payload.append({
            "id_oferta": of.id,
            "es_conjunta": bool(of.es_conjunta or len(of.participaciones) > 1),
            "id_ong": of.creada_por_ong_id or (of.participaciones[0].ong_id if of.participaciones else None),
            "recursos": [
                {
                    "id_recurso": rec_id,
                    "cantidad_ofrecida": cant,
                }
                for rec_id, cant in cant_por_recurso.items()
            ],
        })

    for lote in LoteNecesidades.query.filter_by(emergencia_id=emergencia_id).all():
        if lote.bonita_estado != "validado":
            lote.bonita_estado = "validando"
    db.session.commit()

    return {
        "id_emergencia": emergencia.id,
        "tipo_desastre": tipo_desastre,
        "gravedad": gravedad,
        "ofertas": ofertas_payload,
    }


def enviar_ofertas_a_validar(emergencia_id: int):
    """Envía las ofertas de la emergencia a Bonita para su validación por competencias."""
    from src.core.database import db
    from src.core.models.emergencia import Emergencia
    from src.core.models.lote_necesidades import LoteNecesidades
    from src.core.services.lotes import todos_los_lotes_cubiertos

    emergencia_id = _id(emergencia_id, "ID de emergencia")
    emergencia = db.session.get(Emergencia, emergencia_id)
    if not emergencia:
        raise BonitaError(f"La emergencia {emergencia_id} no existe.")
    if not emergencia.bonita_case_id:
        raise BonitaError(f"La emergencia {emergencia_id} no tiene un caso de Bonita asociado.")

    lotes_emergencia = LoteNecesidades.query.filter_by(emergencia_id=emergencia_id).all()
    estados_previos = {lote.id: lote.bonita_estado for lote in lotes_emergencia}

    cubiertos = todos_los_lotes_cubiertos(emergencia_id)
    payload_validacion = construir_solicitud_validacion(emergencia_id)

    cliente = _ClienteBonita("SISTEMA_NACIONAL")
    try:
        cliente.completar(
            emergencia.bonita_case_id,
            "Validar ofertas",
            {
                "todosLotesCubiertos_input": cubiertos,
                "solicitud_validacion_input": json.dumps(payload_validacion),
            }
        )
    except Exception:
        for lote in lotes_emergencia:
            db.session.refresh(lote)
            if lote.bonita_estado == "validando":
                lote.bonita_estado = estados_previos[lote.id]
        db.session.commit()
        raise


def enviar_adjudicaciones_a_bonita(emergencia_id: int):
    """Envía a Bonita las ofertas adjudicadas y cuenta la cantidad de ONGs participantes."""
    from src.core.database import db
    from src.core.models.emergencia import Emergencia
    from src.core.services.ofertas import detalles_para_convocatoria, listar_ofertas_adjudicadas

    emergencia_id = _id(emergencia_id, "ID de emergencia")
    emergencia = db.session.get(Emergencia, emergencia_id)
    if not emergencia:
        raise BonitaError(f"La emergencia {emergencia_id} no existe.")
    if not emergencia.bonita_case_id:
        raise BonitaError(f"La emergencia {emergencia_id} no tiene un caso de Bonita asociado.")

    adjudicadas = listar_ofertas_adjudicadas(emergencia_id)
    if not adjudicadas:
        raise BonitaError(f"No hay ofertas adjudicadas para la emergencia {emergencia_id}.")

    ongs_unicas = set()
    ofertas_adj_payload = []
    for o in adjudicadas:
        detalles = detalles_para_convocatoria(o)
        cant_por_recurso: dict[int, int] = {}
        for d in detalles:
            ong_det = getattr(d, "id_ong", None) or o.creada_por_ong_id
            if ong_det is not None:
                ongs_unicas.add(ong_det)
            cant_por_recurso[d.id_recurso] = cant_por_recurso.get(d.id_recurso, 0) + int(d.cantidad_adjudicada or d.cantidad)
        if not detalles and o.creada_por_ong_id is not None:
            ongs_unicas.add(o.creada_por_ong_id)
        ofertas_adj_payload.append({
            "id_oferta": o.id,
            "id_ong": o.creada_por_ong_id or (o.participaciones[0].ong_id if o.participaciones else None),
            "recursos": [
                {
                    "id_recurso": rec_id,
                    "cantidad_adjudicada": cant,
                }
                for rec_id, cant in cant_por_recurso.items()
            ],
        })

    ongs_pendientes = len(ongs_unicas)

    payload_adjudicacion = {
        "id_emergencia": emergencia.id,
        "ofertas_adjudicadas": ofertas_adj_payload,
    }

    cliente = _ClienteBonita()
    cliente.completar(
        emergencia.bonita_case_id,
        "Seleccionar ofertas",
        {
            "ongsPendientes_input": ongs_pendientes,
            "solicitud_adjudicacion_input": json.dumps(payload_adjudicacion),
        }
    )


def notificar_cierre_ong(case_id: int, ong_id: int):
    """Notifica a Bonita la finalización total de tareas de una ONG para liberar sus recursos."""
    case_id = _id(case_id, "ID del caso")
    ong_id = _id(ong_id, "ID de ONG")

    cliente = _ClienteBonita("ONG")
    cliente.completar(
        case_id,
        "Marcar fin de actividades",
        {
            "finONG": 1,
            "id_ong_input": ong_id,
        },
        esperar_nueva=True,
    )


_REINTENTOS_ACTIVIDAD: dict[str, dict] = {}
_VIGILANTE_INICIADO = False
_VIGILANTE_LOCK = threading.Lock()


def reintentar_actividades_fallidas(max_intentos: int = 5) -> dict:
    """Consulta actividades en estado failed en Bonita y dispara replay con límite de intentos."""
    from flask import current_app
    from src.core.database import db
    from src.core.models.emergencia import Emergencia
    from src.core.models.lote_necesidades import LoteNecesidades

    config = current_app.config
    if not config.get("BONITA_ADMIN_USERNAME") or not config.get("BONITA_ADMIN_PASSWORD"):
        logger.warning("Vigilante de reintentos Bonita inactivo: faltan BONITA_ADMIN_USERNAME y BONITA_ADMIN_PASSWORD.")
        return {"reintentadas": 0, "agotadas": 0}

    cliente = _ClienteBonita("ADMIN")
    fallidas = cliente.pedir("/API/bpm/activity?p=0&c=100&f=state%3Dfailed", etapa="consultar actividades fallidas")
    if not isinstance(fallidas, list):
        return {"reintentadas": 0, "agotadas": 0}

    ahora = time.monotonic()
    reintentadas = 0
    agotadas = 0

    activas_ids = {str(act.get("id")) for act in fallidas if isinstance(act, dict) and act.get("id")}
    for act_id in list(_REINTENTOS_ACTIVIDAD):
        if act_id not in activas_ids:
            _REINTENTOS_ACTIVIDAD.pop(act_id, None)

    for act in fallidas:
        if not isinstance(act, dict) or not act.get("id"):
            continue
        act_id = str(act["id"])
        case_id = act.get("caseId")
        nombre = act.get("name", act_id)
        estado_reintento = _REINTENTOS_ACTIVIDAD.setdefault(act_id, {"intentos": 0, "proximo": 0.0, "agotado": False})
        if estado_reintento["agotado"]:
            continue

        if estado_reintento["intentos"] >= max_intentos:
            estado_reintento["agotado"] = True
            agotadas += 1
            logger.error(
                "Actividad Bonita %s (%s, caso %s) superó el máximo de %s reintentos; se detiene el replay.",
                act_id, nombre, case_id, max_intentos,
            )
            if case_id:
                try:
                    emergencia = Emergencia.query.filter_by(bonita_case_id=int(case_id)).first()
                    if emergencia:
                        for lote in LoteNecesidades.query.filter_by(emergencia_id=emergencia.id).all():
                            if lote.bonita_estado != "validado":
                                lote.bonita_estado = "fallo_validacion"
                        db.session.commit()
                except Exception as exc:
                    db.session.rollback()
                    logger.warning("No se pudo marcar fallo_validacion para caso %s: %s", case_id, exc)
            continue

        if ahora < estado_reintento["proximo"]:
            continue

        intento = estado_reintento["intentos"] + 1
        try:
            cliente.pedir(f"/API/bpm/activity/{act_id}", "PUT", {"state": "replay"}, f"reintentar actividad {nombre}")
            estado_reintento["intentos"] = intento
            estado_reintento["proximo"] = ahora + min(300, 15 * (2 ** (intento - 1)))
            reintentadas += 1
            logger.warning(
                "Replay #%s/%s disparado para actividad Bonita %s (%s, caso %s).",
                intento, max_intentos, act_id, nombre, case_id,
            )
        except BonitaError as exc:
            logger.warning("Falló el replay de la actividad Bonita %s (%s): %s", act_id, nombre, exc)

    return {"reintentadas": reintentadas, "agotadas": agotadas}


def iniciar_vigilante_reintentos(app):
    """Inicia un hilo daemon que reintenta actividades fallidas en Bonita periódicamente."""
    global _VIGILANTE_INICIADO
    if app.config.get("TESTING") or not app.config.get("BONITA_RETRY_ENABLED", True):
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    with _VIGILANTE_LOCK:
        if _VIGILANTE_INICIADO:
            return
        _VIGILANTE_INICIADO = True

    intervalo = max(5, int(app.config.get("BONITA_RETRY_INTERVAL", 30)))

    def _bucle():
        while True:
            time.sleep(intervalo)
            try:
                with app.app_context():
                    reintentar_actividades_fallidas()
            except Exception as exc:
                logger.warning("Error en vigilante de reintentos Bonita: %s", exc)

    hilo = threading.Thread(target=_bucle, name="bonita-retry-watcher", daemon=True)
    hilo.start()
    app.logger.info("Vigilante de reintentos Bonita iniciado (intervalo %ss).", intervalo)
