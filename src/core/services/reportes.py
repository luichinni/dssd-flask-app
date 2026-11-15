"""Servicios de agregación de métricas locales y de Bonita para el rol Auditor."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import os
import time

from sqlalchemy import func

from src.core.database import db
from src.core.enums import (
    EstadoActividadEnum,
    EstadoOfertaEnum,
    NivelGravedadEnum,
    TipoDesastreEnum,
    TipoRecursoEnum,
)
from src.core.models import (
    ActividadONG,
    DetalleVersionOferta,
    Emergencia,
    LoteDetalle,
    LoteNecesidades,
    Municipio,
    Oferta,
    RecursoCatalogo,
    VersionOferta,
)
from src.core.services.bonita import BonitaError, _ClienteBonita

ORDEN_ETAPAS_BONITA = [
    "Registrar emergencia",
    "Crear lotes de necesidades",
    "Publicar convocatoria",
    "Validar ofertas",
    "Evaluar y decidir curso de acción",
    "Reformular lotes de necesidades",
    "Seleccionar ofertas",
    "Marcar fin de actividades",
]

_BONITA_CACHE: dict[int, tuple[float, list[dict]]] = {}
_BONITA_CACHE_TTL_SEC = 300


def _parse_fecha(valor: str | None, fin_dia: bool = False) -> datetime | None:
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if fin_dia and len(valor.strip()) == 10:
        dt = dt + timedelta(days=1) - timedelta(microseconds=1)
    return dt


def _parse_bonita_dt(valor: str | None) -> datetime | None:
    if not valor:
        return None
    normalizado = str(valor).strip().replace(" ", "T")
    if normalizado.endswith("Z"):
        normalizado = normalizado[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalizado)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _enum_val(val):
    return val.value if hasattr(val, "value") else val


def _filtrar_emergencias_query(filtros: dict):
    query = Emergencia.query
    fecha_desde = _parse_fecha(filtros.get("fecha_desde"))
    fecha_hasta = _parse_fecha(filtros.get("fecha_hasta"), fin_dia=True)
    tipo_desastre = (filtros.get("tipo_desastre") or "").strip()
    nivel_gravedad = (filtros.get("nivel_gravedad") or "").strip()
    municipio_id = (filtros.get("municipio_id") or "").strip()

    if fecha_desde:
        query = query.filter(Emergencia.fecha_registro >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Emergencia.fecha_registro <= fecha_hasta)
    if tipo_desastre:
        try:
            tipo_enum = TipoDesastreEnum(tipo_desastre)
            query = query.filter(Emergencia.tipo_desastre == tipo_enum)
        except ValueError:
            pass
    if nivel_gravedad:
        try:
            query = query.filter(Emergencia.nivel_gravedad == int(nivel_gravedad))
        except ValueError:
            pass
    if municipio_id:
        try:
            query = query.filter(Emergencia.municipio_id == int(municipio_id))
        except ValueError:
            pass
    return query


def obtener_metricas_bonita(emergencias: list[Emergencia], cliente_factory=_ClienteBonita) -> dict:
    """Consulta tiempos promedio por etapa en Bonita para los casos vinculados."""
    case_ids = sorted({e.bonita_case_id for e in emergencias if e.bonita_case_id})
    if not case_ids:
        return {
            "bonita_disponible": False,
            "motivo": "Las emergencias filtradas no tienen casos de Bonita vinculados.",
            "casos_consultados": 0,
            "etapas": [],
        }

    ahora_mono = time.monotonic()
    tareas_por_etapa: dict[str, list[float]] = defaultdict(list)
    casos_ok = 0
    cliente = None

    for case_id in case_ids:
        cached = _BONITA_CACHE.get(case_id)
        tareas = None
        if cached and (ahora_mono - cached[0]) < _BONITA_CACHE_TTL_SEC:
            tareas = cached[1]
        else:
            try:
                if cliente is None:
                    cliente = cliente_factory()
                tareas = cliente.listar_tareas_archivadas_caso(case_id)
                _BONITA_CACHE[case_id] = (ahora_mono, tareas)
            except BonitaError as err:
                if casos_ok == 0:
                    return {
                        "bonita_disponible": False,
                        "motivo": str(err),
                        "casos_consultados": 0,
                        "etapas": [],
                    }
                continue

        casos_ok += 1
        for tarea in tareas or []:
            nombre = tarea.get("name") or tarea.get("displayName")
            inicio = _parse_bonita_dt(tarea.get("reached_state_date"))
            fin = _parse_bonita_dt(tarea.get("archivedDate"))
            if not nombre or not inicio or not fin:
                continue
            horas = max(0.0, (fin - inicio).total_seconds() / 3600.0)
            tareas_por_etapa[nombre].append(horas)

    orden_idx = {nombre: idx for idx, nombre in enumerate(ORDEN_ETAPAS_BONITA)}
    etapas_ordenadas = sorted(
        tareas_por_etapa.keys(),
        key=lambda n: (orden_idx.get(n, 999), n),
    )

    etapas = []
    for nombre in etapas_ordenadas:
        valores = tareas_por_etapa[nombre]
        etapas.append({
            "etapa": nombre,
            "promedio_horas": round(sum(valores) / len(valores), 2),
            "min_horas": round(min(valores), 2),
            "max_horas": round(max(valores), 2),
            "cantidad": len(valores),
        })

    return {
        "bonita_disponible": True,
        "es_demo": False,
        "motivo": None,
        "casos_consultados": casos_ok,
        "etapas": etapas,
    }


def _tiempos_bonita_demo(emergencias: list[Emergencia], motivo: str | None) -> dict:
    """Genera tiempos simulados por etapa BPMN cuando Bonita no está disponible."""
    if not emergencias:
        return {
            "bonita_disponible": False,
            "es_demo": True,
            "motivo": "No hay emergencias para los filtros seleccionados.",
            "casos_consultados": 0,
            "etapas": [],
        }
    base_etapas = [
        ("Registrar emergencia", 0.5, 0.2, 1.1),
        ("Crear lotes de necesidades", 3.2, 1.5, 6.0),
        ("Publicar convocatoria", 1.8, 0.8, 4.0),
        ("Validar ofertas", 6.5, 2.0, 14.0),
        ("Evaluar y decidir curso de acción", 4.1, 1.0, 9.5),
        ("Reformular lotes de necesidades", 5.0, 2.5, 8.0),
        ("Seleccionar ofertas", 3.8, 1.2, 7.5),
        ("Marcar fin de actividades", 148.0, 48.0, 264.0),
    ]
    n = len(emergencias)
    etapas = [
        {
            "etapa": nombre,
            "promedio_horas": prom,
            "min_horas": mn,
            "max_horas": mx,
            "cantidad": max(1, n // 2) if "Reformular" in nombre else n,
        }
        for nombre, prom, mn, mx in base_etapas
    ]
    return {
        "bonita_disponible": False,
        "es_demo": True,
        "motivo": f"Bonita offline ({motivo or 'sin conexión'}): mostrando tiempos simulados de ejemplo.",
        "casos_consultados": n,
        "etapas": etapas,
    }


def obtener_reporte_auditor(filtros: dict | None = None, cliente_factory=_ClienteBonita) -> dict:
    """Genera KPIs, series para gráficos y tablas estructuradas para Auditor/Directivo."""
    filtros = filtros or {}
    emergencias = _filtrar_emergencias_query(filtros).order_by(Emergencia.fecha_registro.asc()).all()
    emergencia_ids = [e.id for e in emergencias]

    # 1. KPIs de emergencias
    total_emergencias = len(emergencias)
    cerradas = sum(1 for e in emergencias if e.bonita_estado == "finalizada")
    activas = total_emergencias - cerradas

    # 2. Ofertas y consorcios (sobre ofertas adjudicadas de las emergencias filtradas)
    ofertas_adj = []
    if emergencia_ids:
        ofertas_adj = (
            Oferta.query
            .filter(Oferta.id_emergencia.in_(emergencia_ids))
            .filter(Oferta.estado == EstadoOfertaEnum.ADJUDICADA)
            .all()
        )
    total_adj = len(ofertas_adj)
    consorcios_cant = sum(1 for o in ofertas_adj if o.es_conjunta)
    individuales_cant = total_adj - consorcios_cant
    pct_consorcios = round((consorcios_cant / total_adj) * 100, 1) if total_adj else 0.0

    # 3. Suministros movilizados (DetalleVersionOferta.cantidad_adjudicada)
    suministros_mes_cat: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    top_recursos_map: dict[tuple[str, str], int] = defaultdict(int)
    total_suministros = 0

    if ofertas_adj:
        detalles_rows = (
            db.session.query(
                Oferta.fecha_ultima_modificacion,
                RecursoCatalogo.nombre,
                RecursoCatalogo.tipo_recursos,
                RecursoCatalogo.unidad_medida,
                DetalleVersionOferta.cantidad_adjudicada,
            )
            .join(VersionOferta, VersionOferta.id_oferta == Oferta.id)
            .join(DetalleVersionOferta, DetalleVersionOferta.id_version == VersionOferta.id)
            .join(RecursoCatalogo, RecursoCatalogo.id == DetalleVersionOferta.id_recurso)
            .filter(Oferta.id.in_([o.id for o in ofertas_adj]))
            .filter(VersionOferta.numero_version == Oferta.version_actual)
            .filter(DetalleVersionOferta.cantidad_adjudicada > 0)
            .all()
        )
        for fecha_mod, rec_nombre, tipo_rec, unidad, cant_adj in detalles_rows:
            mes = fecha_mod.strftime("%Y-%m") if fecha_mod else "Sin fecha"
            cat = _enum_val(tipo_rec)
            suministros_mes_cat[mes][cat] += int(cant_adj)
            top_recursos_map[(rec_nombre, unidad)] += int(cant_adj)
            total_suministros += int(cant_adj)

    meses_ordenados = sorted(suministros_mes_cat.keys())
    categorias_recurso = [t.value for t in TipoRecursoEnum]
    series_suministros = {
        cat: [suministros_mes_cat[m].get(cat, 0) for m in meses_ordenados]
        for cat in categorias_recurso
    }
    top_recursos = [
        {"nombre": nombre, "unidad": unidad, "cantidad": cant}
        for (nombre, unidad), cant in sorted(top_recursos_map.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    # 4. Estado de actividades ("proyectos") y cobertura de lotes
    lotes = []
    if emergencia_ids:
        lotes = LoteNecesidades.query.filter(LoteNecesidades.emergencia_id.in_(emergencia_ids)).all()
    lote_ids = [l.id for l in lotes]

    actividades = []
    if lote_ids:
        actividades = ActividadONG.query.filter(ActividadONG.lote_referencia.in_(lote_ids)).all()

    act_finalizadas = [a for a in actividades if a.estado == EstadoActividadEnum.FINALIZADA]
    act_en_ejecucion = [a for a in actividades if a.estado == EstadoActividadEnum.EN_EJECUCION]
    con_informe = sum(1 for a in act_finalizadas if (a.informe_cierre or "").strip())
    duraciones_dias = [
        max(0.0, (a.fecha_finalizacion - a.fecha_inicio).total_seconds() / 86400.0)
        for a in act_finalizadas
        if a.fecha_finalizacion and a.fecha_inicio
    ]
    prom_dias_act = round(sum(duraciones_dias) / len(duraciones_dias), 1) if duraciones_dias else 0.0
    tasa_fin_act = round((len(act_finalizadas) / len(actividades)) * 100, 1) if actividades else 0.0

    # Cobertura por categoría de recurso (Necesario vs Mínimo vs Adjudicado)
    cob_nec = defaultdict(int)
    cob_min = defaultdict(int)
    cob_adj = defaultdict(int)
    if lote_ids:
        lote_det_rows = (
            db.session.query(
                RecursoCatalogo.tipo_recursos,
                func.sum(LoteDetalle.cantidad_necesaria),
                func.sum(LoteDetalle.cantidad_minima),
            )
            .join(RecursoCatalogo, RecursoCatalogo.id == LoteDetalle.id_recurso)
            .filter(LoteDetalle.lote_id.in_(lote_ids))
            .group_by(RecursoCatalogo.tipo_recursos)
            .all()
        )
        for tipo_rec, s_nec, s_min in lote_det_rows:
            cat = _enum_val(tipo_rec)
            cob_nec[cat] += int(s_nec or 0)
            cob_min[cat] += int(s_min or 0)
        for m in meses_ordenados:
            for cat in categorias_recurso:
                cob_adj[cat] += suministros_mes_cat[m].get(cat, 0)

    # 5. Emergencias por tipo de desastre, gravedad y municipio
    gravedad_labels = {
        NivelGravedadEnum.BAJO.value: "Bajo",
        NivelGravedadEnum.MEDIO.value: "Medio",
        NivelGravedadEnum.ALTO.value: "Alto",
        NivelGravedadEnum.CRITICO.value: "Crítico",
    }
    tipo_grav_map: dict[str, dict[str, int]] = {
        t.value: {g: 0 for g in gravedad_labels.values()} for t in TipoDesastreEnum
    }
    muni_counts: dict[str, int] = defaultdict(int)
    for e in emergencias:
        t_val = _enum_val(e.tipo_desastre)
        g_val = gravedad_labels.get(e.nivel_gravedad, "Medio")
        if t_val in tipo_grav_map:
            tipo_grav_map[t_val][g_val] += 1
        muni_label = f"{e.municipio.nombre} ({e.municipio.provincia})" if e.municipio else "Sin municipio"
        muni_counts[muni_label] += 1

    top_municipios = [
        {"municipio": k, "cantidad": v}
        for k, v in sorted(muni_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    # 6. Tiempos desde Bonita (con fallback demo si Bonita está offline)
    tiempos_bonita = obtener_metricas_bonita(emergencias, cliente_factory=cliente_factory)
    usar_demo = os.environ.get("BONITA_DEMO_FALLBACK", "true").lower() == "true"
    if not tiempos_bonita.get("bonita_disponible") and usar_demo:
        tiempos_bonita = _tiempos_bonita_demo(emergencias, tiempos_bonita.get("motivo"))

    # Opciones para selects de filtro
    municipios_all = Municipio.query.order_by(Municipio.nombre.asc()).all()

    return {
        "filtros_aplicados": {
            "fecha_desde": filtros.get("fecha_desde") or "",
            "fecha_hasta": filtros.get("fecha_hasta") or "",
            "tipo_desastre": filtros.get("tipo_desastre") or "",
            "nivel_gravedad": filtros.get("nivel_gravedad") or "",
            "municipio_id": filtros.get("municipio_id") or "",
        },
        "opciones_filtro": {
            "tipos_desastre": [t.value for t in TipoDesastreEnum],
            "niveles_gravedad": [{"valor": k, "etiqueta": v} for k, v in gravedad_labels.items()],
            "municipios": [{"id": m.id, "nombre": f"{m.nombre} ({m.provincia})"} for m in municipios_all],
        },
        "kpis": {
            "total_emergencias": total_emergencias,
            "emergencias_activas": activas,
            "emergencias_cerradas": cerradas,
            "total_suministros": total_suministros,
            "ofertas_adjudicadas": total_adj,
            "ofertas_consorcio": consorcios_cant,
            "pct_consorcios": pct_consorcios,
            "total_actividades": len(actividades),
            "actividades_finalizadas": len(act_finalizadas),
            "actividades_en_ejecucion": len(act_en_ejecucion),
            "tasa_finalizacion_actividades": tasa_fin_act,
            "actividades_con_informe": con_informe,
            "promedio_dias_actividad": prom_dias_act,
        },
        "graficos": {
            "suministros_mensuales": {
                "meses": meses_ordenados,
                "categorias": categorias_recurso,
                "series": series_suministros,
            },
            "top_recursos": top_recursos,
            "consorcios": {
                "etiquetas": ["Consorcio (Conjunta)", "Individual"],
                "valores": [consorcios_cant, individuales_cant],
                "porcentaje_consorcio": pct_consorcios,
            },
            "actividades_estado": {
                "etiquetas": ["Finalizadas", "En Ejecución"],
                "valores": [len(act_finalizadas), len(act_en_ejecucion)],
                "con_informe": con_informe,
            },
            "cobertura_lotes": {
                "categorias": categorias_recurso,
                "necesaria": [cob_nec[c] for c in categorias_recurso],
                "minima": [cob_min[c] for c in categorias_recurso],
                "adjudicada": [cob_adj[c] for c in categorias_recurso],
            },
            "tiempos_bonita": tiempos_bonita,
            "emergencias_tipo_gravedad": {
                "tipos": [t.value for t in TipoDesastreEnum],
                "niveles": list(gravedad_labels.values()),
                "series": {
                    nivel: [tipo_grav_map[t.value][nivel] for t in TipoDesastreEnum]
                    for nivel in gravedad_labels.values()
                },
            },
            "emergencias_municipio": top_municipios,
        },
    }
