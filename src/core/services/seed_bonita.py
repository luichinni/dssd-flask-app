"""Orquestador de casos reales de prueba en Bonita BPM hasta su archivo final."""
import json
import logging
import time
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.core.database import db
from src.core.enums import (
    AccionPostOfertaEnum,
    EstadoActividadEnum,
    NivelGravedadEnum,
    TipoDesastreEnum,
)
from src.core.models.actividad import ActividadONG
from src.core.models.emergencia import Emergencia
from src.core.models.inventario import InventarioONG
from src.core.models.lote_necesidades import LoteNecesidades
from src.core.models.municipio import Municipio
from src.core.models.oferta import Oferta
from src.core.models.ong import ONG
from src.core.models.recurso_catalogo import RecursoCatalogo
from src.core.models.user import Usuario
from src.core.services.actividades import finalizar_actividad
from src.core.services.bonita import (
    BonitaError,
    _ClienteBonita,
    completar_decision_post_convocatoria,
    enviar_adjudicaciones_a_bonita,
    resolver_process_definition_id,
)
from src.core.services.emergencias import crear_emergencia
from src.core.services.lotes import (
    continuar_con_ofertas_disponibles,
    publicar_lote,
    reabrir_convocatoria,
)
from src.core.services.ofertas import (
    adjudicar_oferta,
    crear_oferta,
    listar_ofertas_aceptadas,
    modificar_oferta,
)
from src.core.timezone import a_argentina, ahora_ar

logger = logging.getLogger(__name__)

ESCENARIOS_BPM = [
    {
        "codigo": "camino_feliz_ong_unica",
        "zona": "[BPM] Alerta Hidrológica - Ribera Berisso",
        "descripcion": "Caso histórico completo por camino feliz con una sola ONG.",
        "tipo_desastre": TipoDesastreEnum.hidrologico,
        "nivel_gravedad": NivelGravedadEnum.ALTO.value,
        "municipio": "La Plata",
        "lote": [("Raciones de Alimento Seco", 100, 80)],
        "ofertas_iniciales": [
            {"ong": "principal", "recursos": [("Raciones de Alimento Seco", 100)]},
        ],
        "accion": None,
    },
    {
        "codigo": "camino_feliz_consorcio",
        "zona": "[BPM] Temporal Severo - Consorcio Bahía Blanca",
        "descripcion": "Caso histórico completo con oferta colaborativa entre dos ONGs.",
        "tipo_desastre": TipoDesastreEnum.meteorologico,
        "nivel_gravedad": NivelGravedadEnum.CRITICO.value,
        "municipio": "Bahía Blanca",
        "lote": [
            ("Paramédicos de Emergencia", 10, 8),
            ("Kits de Higiene Comunitarios", 40, 30),
        ],
        "ofertas_iniciales": [
            {
                "ong": "principal",
                "recursos": [("Paramédicos de Emergencia", 10)],
                "colaboradora": "colaboradora",
                "recursos_colaboradora": [("Kits de Higiene Comunitarios", 40)],
            },
        ],
        "accion": None,
    },
    {
        "codigo": "reabrir_convocatoria",
        "zona": "[BPM] Incendio Sierras - Reapertura Córdoba",
        "descripcion": "Caso histórico con primera ventana sin cobertura mínima y reapertura exitosa.",
        "tipo_desastre": TipoDesastreEnum.incendio_forestal,
        "nivel_gravedad": NivelGravedadEnum.ALTO.value,
        "municipio": "Córdoba Capital",
        "lote": [("Carpas Sanitarias de Campaña", 10, 8)],
        "ofertas_iniciales": [
            {"ong": "principal", "recursos": [("Carpas Sanitarias de Campaña", 3)]},
        ],
        "accion": AccionPostOfertaEnum.REABRIR,
        "ofertas_reapertura": [
            {"ong": "colaboradora", "recursos": [("Carpas Sanitarias de Campaña", 6)]},
        ],
    },
    {
        "codigo": "continuar_parcial",
        "zona": "[BPM] Emergencia Sanitaria - Cobertura Parcial Rosario",
        "descripcion": "Caso histórico con cobertura parcial resuelto mediante decisión CONTINUAR.",
        "tipo_desastre": TipoDesastreEnum.biologico,
        "nivel_gravedad": NivelGravedadEnum.MEDIO.value,
        "municipio": "Rosario",
        "lote": [("Ambulancia de Traslado 4x4", 6, 5)],
        "ofertas_iniciales": [
            {"ong": "principal", "recursos": [("Ambulancia de Traslado 4x4", 2)]},
        ],
        "accion": AccionPostOfertaEnum.CONTINUAR,
    },
]


def _http_json(url: str, method: str = "GET", payload: dict | None = None, headers: dict | None = None) -> dict:
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    data = None
    if payload is not None:
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=req_headers, method=method)
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolver_api_externa_base() -> str:
    candidatos = ["http://host.docker.internal:8000", "http://localhost:8000"]
    for base in candidatos:
        try:
            auth = _http_json(
                f"{base}/api/v1/auth/login",
                method="POST",
                payload={"email": "operador@emergencias.gob.ar", "password": "PasswordSegura123!"},
            )
            if auth.get("access_token"):
                return base
        except (HTTPError, URLError, TimeoutError, ValueError):
            continue
    raise BonitaError(
        "No se pudo conectar/autenticar con la API externa en puerto 8000. "
        "Verificá que DSSD-Servicio-Externo esté levantado y seedeado."
    )


def _verificar_precondiciones(ongs_ids: set[int], recursos_ids: set[int]) -> None:
    resolver_process_definition_id()
    base_ext = _resolver_api_externa_base()
    auth = _http_json(
        f"{base_ext}/api/v1/auth/login",
        method="POST",
        payload={"email": "operador@emergencias.gob.ar", "password": "PasswordSegura123!"},
    )
    token = auth["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    try:
        ongs_resp = _http_json(f"{base_ext}/api/v1/ongs/habilitadas", headers=headers)
        ongs_ext = {int(o["id_ong"]) for o in ongs_resp.get("ongs", [])}
        faltan_ongs = sorted(ongs_ids - ongs_ext)
        if faltan_ongs:
            raise BonitaError(
                f"Faltan ONGs habilitadas en la API externa: {faltan_ongs}. "
                "Ejecutá 'python -m app.cli.seed_certificaciones_demo' en DSSD-Servicio-Externo."
            )

        disp_resp = _http_json(f"{base_ext}/api/v1/recursos/disponibilidad", headers=headers)
        pares_ok = {
            (int(item["id_ong"]), int(item["id_recurso"])): int(item["inventario_actual"])
            for item in disp_resp.get("recursos", [])
        }
        faltan_inv = [
            (oid, rid)
            for oid in sorted(ongs_ids)
            for rid in sorted(recursos_ids)
            if pares_ok.get((oid, rid), 0) < 100
        ]
        if faltan_inv:
            raise BonitaError(
                f"Falta stock suficiente en la API externa para {faltan_inv}. "
                "Ejecutá 'python -m app.cli.seed_certificaciones_demo' en DSSD-Servicio-Externo."
            )
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        raise BonitaError(f"Error consultando catálogo en la API externa: {exc}") from exc


def _asegurar_inventario_local(ong_ids: list[int], recursos_map: dict[str, RecursoCatalogo]) -> dict[tuple[int, int], InventarioONG]:
    inventarios: dict[tuple[int, int], InventarioONG] = {}
    for ong_id in ong_ids:
        for recurso in recursos_map.values():
            item = InventarioONG.query.filter_by(ong_id=ong_id, id_recurso=recurso.id).first()
            if item is None:
                item = InventarioONG(
                    ong_id=ong_id,
                    id_recurso=recurso.id,
                    cantidad_total=5000,
                    cantidad_disponible=5000,
                )
                db.session.add(item)
            elif item.cantidad_total < 5000:
                item.cantidad_total = 5000
                item.cantidad_disponible = max(item.cantidad_disponible, 5000)
            db.session.flush()
            inventarios[(ong_id, recurso.id)] = item
    db.session.commit()
    return inventarios


def _limpiar_incompleto(zona: str) -> None:
    previas = Emergencia.query.filter_by(zona_afectada=zona).all()
    for em in previas:
        lote_ids = [l.id for l in em.lotes]
        if lote_ids:
            ActividadONG.query.filter(ActividadONG.lote_referencia.in_(lote_ids)).delete(synchronize_session=False)
        for oferta in Oferta.query.filter_by(id_emergencia=em.id).all():
            db.session.delete(oferta)
        db.session.flush()
        db.session.delete(em)
    if previas:
        db.session.commit()


def _esperar_validacion_lote(lote_id: int, case_id: int, timeout: float = 75.0) -> LoteNecesidades:
    deadline = time.monotonic() + timeout
    while True:
        db.session.expire_all()
        lote = db.session.get(LoteNecesidades, lote_id)
        if lote is None:
            raise BonitaError(f"El lote {lote_id} desapareció durante la validación.")
        if lote.bonita_estado == "validado":
            return lote
        if lote.bonita_estado == "fallo_validacion":
            raise BonitaError(f"La validación automática del lote {lote_id} (caso {case_id}) falló.")
        if time.monotonic() >= deadline:
            raise BonitaError(
                f"Timeout esperando validación automática del lote {lote_id} (caso {case_id}, estado={lote.bonita_estado})."
            )
        time.sleep(1.0)


def _esperar_tarea_lista(cliente: _ClienteBonita, case_id: int, nombre: str, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        tareas = cliente.tareas(case_id)
        if any(t.get("name") == nombre and t.get("state") == "ready" for t in tareas):
            return
        if time.monotonic() >= deadline:
            raise BonitaError(f"La tarea '{nombre}' no apareció lista en el caso {case_id}.")
        time.sleep(0.5)


def _esperar_caso_archivado(cliente: _ClienteBonita, case_id: int, timeout: float = 45.0) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        archivado = cliente.obtener_caso_archivado(case_id)
        if archivado is not None:
            return archivado
        if time.monotonic() >= deadline:
            raise BonitaError(f"El caso Bonita {case_id} no finalizó ni se archivó dentro del tiempo esperado.")
        time.sleep(0.5)


def _crear_ofertas_escenario(
    lote_id: int,
    definiciones: list[dict],
    ongs_ctx: dict[str, tuple[int, int]],
    recursos_map: dict[str, RecursoCatalogo],
    inventarios: dict[tuple[int, int], InventarioONG],
) -> None:
    for item in definiciones:
        ong_id, user_id = ongs_ctx[item["ong"]]
        recs = [
            {
                "id_recurso": inventarios[(ong_id, recursos_map[nombre].id)].id,
                "cantidad": cant,
            }
            for nombre, cant in item["recursos"]
        ]
        colabs = ()
        if item.get("colaboradora"):
            colab_id, colab_user_id = ongs_ctx[item["colaboradora"]]
            colabs = (colab_id,)
        oferta = crear_oferta(
            convocatoria_id=lote_id,
            recursos=recs,
            ong_id=ong_id,
            usuario_id=user_id,
            colaboradoras_ids=colabs,
        )
        if item.get("colaboradora") and item.get("recursos_colaboradora"):
            colab_id, colab_user_id = ongs_ctx[item["colaboradora"]]
            recs_colab = [
                {
                    "id_recurso": inventarios[(colab_id, recursos_map[nombre].id)].id,
                    "cantidad": cant,
                }
                for nombre, cant in item["recursos_colaboradora"]
            ]
            modificar_oferta(oferta.id, recs_colab, colab_id, colab_user_id)


def ejecutar_seed_bonita(limite: int = 4, ventana_segundos: int = 12) -> dict:
    """Genera e impulsa casos reales en Bonita BPM hasta su archivo y estado finalizada."""
    operador = Usuario.query.filter_by(email="operador@municipio.gob.ar").first()
    u_ong1 = Usuario.query.filter_by(email="ong@ayuda.org").first()
    u_ong2 = Usuario.query.filter_by(email="colaboradora@ayuda.org").first()
    if not (operador and u_ong1 and u_ong2):
        raise BonitaError("Faltan usuarios base. Ejecutá 'flask seed-db' primero.")

    ong1_id = int((u_ong1.datos_adicionales or {}).get("ong_id", 0))
    ong2_id = int((u_ong2.datos_adicionales or {}).get("ong_id", 0))
    if not (db.session.get(ONG, ong1_id) and db.session.get(ONG, ong2_id)):
        raise BonitaError("Faltan perfiles de ONG base. Ejecutá 'flask seed-db' primero.")

    recursos_map = {r.nombre: r for r in RecursoCatalogo.query.all()}
    if len(recursos_map) < 5:
        raise BonitaError("Faltan recursos en RecursoCatalogo. Ejecutá 'flask seed-db' primero.")

    municipios_map = {m.nombre: m for m in Municipio.query.all()}
    _verificar_precondiciones({ong1_id, ong2_id}, {r.id for r in recursos_map.values()})
    inventarios = _asegurar_inventario_local([ong1_id, ong2_id], recursos_map)

    ongs_ctx = {
        "principal": (ong1_id, u_ong1.id),
        "colaboradora": (ong2_id, u_ong2.id),
    }

    cliente_base = _ClienteBonita()
    cliente_ccr = _ClienteBonita("CCR")
    creados = []
    omitidos = []

    for esc in ESCENARIOS_BPM[:max(0, limite)]:
        existente = Emergencia.query.filter_by(zona_afectada=esc["zona"]).first()
        if (
            existente is not None
            and existente.bonita_estado == "finalizada"
            and existente.bonita_case_id
            and cliente_base.obtener_caso_archivado(existente.bonita_case_id) is not None
        ):
            omitidos.append({"zona": esc["zona"], "case_id": existente.bonita_case_id})
            continue

        _limpiar_incompleto(esc["zona"])

        muni = municipios_map.get(esc["municipio"]) or next(iter(municipios_map.values()))
        emergencia = crear_emergencia(
            tipo_desastre=esc["tipo_desastre"],
            nivel_gravedad=esc["nivel_gravedad"],
            zona_afectada=esc["zona"],
            descripcion=esc["descripcion"],
            reportante_id=operador.id,
            municipio_id=muni.id,
        )
        if not emergencia.bonita_case_id:
            raise BonitaError(f"No se pudo iniciar caso Bonita para '{esc['zona']}'.")
        case_id = int(emergencia.bonita_case_id)

        detalles_lote = [
            {
                "recurso_id": recursos_map[nombre].id,
                "cantidad_necesaria": cant_nec,
                "min_r": min_r,
            }
            for nombre, cant_nec, min_r in esc["lote"]
        ]
        cierre_inicial = ahora_ar() + timedelta(seconds=ventana_segundos)
        lote = publicar_lote(emergencia.id, detalles_lote, cierre_inicial)
        if lote.bonita_estado != "sincronizado":
            raise BonitaError(f"No se pudo publicar el lote {lote.id} en Bonita (caso {case_id}).")

        _crear_ofertas_escenario(lote.id, esc["ofertas_iniciales"], ongs_ctx, recursos_map, inventarios)
        lote = _esperar_validacion_lote(lote.id, case_id)

        restante = (a_argentina(lote.fecha_cierre_ofertas) - ahora_ar()).total_seconds()
        if restante > 0:
            time.sleep(restante + 0.5)

        if esc["accion"] == AccionPostOfertaEnum.REABRIR:
            _esperar_tarea_lista(cliente_ccr, case_id, "Evaluar y decidir curso de acción")
            nueva_fecha = ahora_ar() + timedelta(seconds=ventana_segundos)
            lote = reabrir_convocatoria(lote.id, nueva_fecha)
            completar_decision_post_convocatoria(case_id, AccionPostOfertaEnum.REABRIR, nueva_fecha)
            _crear_ofertas_escenario(lote.id, esc["ofertas_reapertura"], ongs_ctx, recursos_map, inventarios)
            lote = _esperar_validacion_lote(lote.id, case_id)
            restante_re = (a_argentina(lote.fecha_cierre_ofertas) - ahora_ar()).total_seconds()
            if restante_re > 0:
                time.sleep(restante_re + 0.5)
        elif esc["accion"] == AccionPostOfertaEnum.CONTINUAR:
            _esperar_tarea_lista(cliente_ccr, case_id, "Evaluar y decidir curso de acción")
            continuar_con_ofertas_disponibles(lote.id)
            completar_decision_post_convocatoria(case_id, AccionPostOfertaEnum.CONTINUAR)

        _esperar_tarea_lista(cliente_base, case_id, "Seleccionar ofertas")
        aceptadas = listar_ofertas_aceptadas(emergencia.id)
        if not aceptadas:
            raise BonitaError(f"No quedaron ofertas aceptadas para adjudicar en caso {case_id}.")
        for oferta in aceptadas:
            adjudicar_oferta(oferta.id, emergencia_id=emergencia.id)
        enviar_adjudicaciones_a_bonita(emergencia.id)

        actividades = ActividadONG.query.filter_by(lote_referencia=lote.id).order_by(ActividadONG.id.asc()).all()
        if not actividades:
            raise BonitaError(f"No se generaron actividades de despliegue para el lote {lote.id}.")
        for act in actividades:
            if act.estado != EstadoActividadEnum.FINALIZADA:
                finalizar_actividad(
                    act.id,
                    act.ong_id,
                    informe_cierre=f"Cierre operativo automático del escenario {esc['codigo']}.",
                    recursos_utilizados="Recursos desplegados y liberados según protocolo.",
                )
                time.sleep(1.0)

        _esperar_caso_archivado(cliente_base, case_id)
        emergencia = db.session.get(Emergencia, emergencia.id)
        emergencia.bonita_estado = "finalizada"
        db.session.commit()
        creados.append({"zona": esc["zona"], "emergencia_id": emergencia.id, "case_id": case_id})
        logger.info("Caso Bonita %s (%s) finalizado y archivado.", case_id, esc["codigo"])

    return {"creados": creados, "omitidos": omitidos}
