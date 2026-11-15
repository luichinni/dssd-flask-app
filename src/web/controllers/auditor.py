"""Controlador y exportaciones de reportes para el rol Auditor / Directivo."""
from __future__ import annotations

import base64
import csv
import io
import json
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, render_template, request, send_file
from flask_login import current_user, login_required
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from src.core.enums import RolEnum
from src.core.services.reportes import obtener_reporte_auditor
from src.web.decorators.roles_required import roles_required

auditor_bp = Blueprint("auditor", __name__, url_prefix="/auditor")

ALL_CHART_KEYS = {
    "suministros_mensuales",
    "top_recursos",
    "consorcios",
    "actividades_estado",
    "cobertura_lotes",
    "tiempos_bonita",
    "emergencias_tipo_gravedad",
    "emergencias_municipio",
}


def _filtros_desde_request(source=None) -> dict:
    src = source if source is not None else request.args
    return {
        "fecha_desde": (src.get("fecha_desde") or "").strip(),
        "fecha_hasta": (src.get("fecha_hasta") or "").strip(),
        "tipo_desastre": (src.get("tipo_desastre") or "").strip(),
        "nivel_gravedad": (src.get("nivel_gravedad") or "").strip(),
        "municipio_id": (src.get("municipio_id") or "").strip(),
    }


def _graficos_seleccionados(source=None) -> set[str]:
    src = source if source is not None else request.args
    raw = (src.get("graficos") or "").strip()
    if not raw:
        return set(ALL_CHART_KEYS)
    seleccion = {g.strip() for g in raw.split(",") if g.strip() in ALL_CHART_KEYS}
    return seleccion


def _fecha_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")


@auditor_bp.get("/reportes")
@login_required
@roles_required(RolEnum.AUDITOR)
def reportes():
    datos_iniciales = obtener_reporte_auditor(_filtros_desde_request())
    return render_template("auditor/reportes.html", datos=datos_iniciales)


@auditor_bp.get("/reportes/data")
@login_required
@roles_required(RolEnum.AUDITOR)
def reportes_data():
    datos = obtener_reporte_auditor(_filtros_desde_request())
    return jsonify(datos)


@auditor_bp.get("/reportes/export/json")
@login_required
@roles_required(RolEnum.AUDITOR)
def export_json():
    datos = obtener_reporte_auditor(_filtros_desde_request())
    seleccion = _graficos_seleccionados()
    datos_filtrados = {
        **datos,
        "graficos": {k: v for k, v in datos["graficos"].items() if k in seleccion},
    }
    contenido = json.dumps(datos_filtrados, ensure_ascii=False, indent=2)
    return Response(
        contenido,
        mimetype="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="reporte_auditor_{_fecha_tag()}.json"'
        },
    )


@auditor_bp.get("/reportes/export/csv")
@login_required
@roles_required(RolEnum.AUDITOR)
def export_csv():
    datos = obtener_reporte_auditor(_filtros_desde_request())
    seleccion = _graficos_seleccionados()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Sección", "Indicador / Categoría", "Subcategoría", "Valor", "Unidad / Detalle"])
    for clave, valor in datos["kpis"].items():
        writer.writerow(["KPIs", clave, "-", valor, "-"])

    if "suministros_mensuales" in seleccion:
        sum_mens = datos["graficos"]["suministros_mensuales"]
        for idx, mes in enumerate(sum_mens["meses"]):
            for cat in sum_mens["categorias"]:
                writer.writerow(["Suministros Mensuales", mes, cat, sum_mens["series"][cat][idx], "Unidades"])

    if "top_recursos" in seleccion:
        for rec in datos["graficos"]["top_recursos"]:
            writer.writerow(["Top Recursos", rec["nombre"], "-", rec["cantidad"], rec["unidad"]])

    if "consorcios" in seleccion:
        cons = datos["graficos"]["consorcios"]
        for etiqueta, val in zip(cons["etiquetas"], cons["valores"]):
            writer.writerow(["Consorcios", etiqueta, "-", val, f"{cons['porcentaje_consorcio']}% consorcio"])

    if "actividades_estado" in seleccion:
        act = datos["graficos"]["actividades_estado"]
        for etiqueta, val in zip(act["etiquetas"], act["valores"]):
            writer.writerow(["Actividades", etiqueta, "-", val, f"Con informe: {act['con_informe']}"])

    if "cobertura_lotes" in seleccion:
        cob = datos["graficos"]["cobertura_lotes"]
        for i, cat in enumerate(cob["categorias"]):
            writer.writerow(["Cobertura de Lotes", cat, "Necesaria / Mínima / Adjudicada", f"{cob['necesaria'][i]} / {cob['minima'][i]} / {cob['adjudicada'][i]}", "Unidades"])

    if "tiempos_bonita" in seleccion:
        for etapa in datos["graficos"]["tiempos_bonita"]["etapas"]:
            writer.writerow([
                "Tiempos Bonita",
                etapa["etapa"],
                f"Casos/Tareas: {etapa['cantidad']}",
                etapa["promedio_horas"],
                f"Min: {etapa['min_horas']}h / Max: {etapa['max_horas']}h",
            ])

    if "emergencias_tipo_gravedad" in seleccion:
        tg = datos["graficos"]["emergencias_tipo_gravedad"]
        for i, tipo in enumerate(tg["tipos"]):
            for nivel in tg["niveles"]:
                writer.writerow(["Emergencias Tipo/Gravedad", tipo, nivel, tg["series"][nivel][i], "Emergencias"])

    if "emergencias_municipio" in seleccion:
        for muni in datos["graficos"]["emergencias_municipio"]:
            writer.writerow(["Emergencias por Municipio", muni["municipio"], "-", muni["cantidad"], "Emergencias"])

    csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")
    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="reporte_auditor_{_fecha_tag()}.csv"'
        },
    )


def _autoajustar_hoja(ws):
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 4, 14), 48)


def _estilizar_cabecera(ws):
    fill = PatternFill(start_color="312E81", end_color="312E81", fill_type="solid")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font


@auditor_bp.get("/reportes/export/xlsx")
@login_required
@roles_required(RolEnum.AUDITOR)
def export_xlsx():
    datos = obtener_reporte_auditor(_filtros_desde_request())
    seleccion = _graficos_seleccionados()
    wb = Workbook()

    # 1. Resumen KPIs (siempre presente)
    ws_kpi = wb.active
    ws_kpi.title = "Resumen KPIs"
    ws_kpi.append(["Indicador", "Valor"])
    for k, v in datos["kpis"].items():
        ws_kpi.append([k.replace("_", " ").capitalize(), v])
    _estilizar_cabecera(ws_kpi)
    _autoajustar_hoja(ws_kpi)

    # 2. Suministros
    if "suministros_mensuales" in seleccion or "top_recursos" in seleccion:
        ws_sum = wb.create_sheet("Suministros")
        if "suministros_mensuales" in seleccion:
            sum_mens = datos["graficos"]["suministros_mensuales"]
            ws_sum.append(["Mes", *sum_mens["categorias"]])
            for idx, mes in enumerate(sum_mens["meses"]):
                ws_sum.append([mes, *[sum_mens["series"][c][idx] for c in sum_mens["categorias"]]])
            ws_sum.append([])
        if "top_recursos" in seleccion:
            ws_sum.append(["Top Recursos", "Unidad", "Cantidad Adjudicada"])
            for rec in datos["graficos"]["top_recursos"]:
                ws_sum.append([rec["nombre"], rec["unidad"], rec["cantidad"]])
        _estilizar_cabecera(ws_sum)
        _autoajustar_hoja(ws_sum)

    # 3. Consorcios
    if "consorcios" in seleccion:
        ws_cons = wb.create_sheet("Consorcios")
        ws_cons.append(["Modalidad", "Cantidad Ofertas Adjudicadas", "% Consorcio Global"])
        cons = datos["graficos"]["consorcios"]
        for etiqueta, val in zip(cons["etiquetas"], cons["valores"]):
            ws_cons.append([etiqueta, val, cons["porcentaje_consorcio"]])
        _estilizar_cabecera(ws_cons)
        _autoajustar_hoja(ws_cons)

    # 4. Actividades y Cobertura
    if "actividades_estado" in seleccion or "cobertura_lotes" in seleccion:
        ws_act = wb.create_sheet("Actividades")
        if "actividades_estado" in seleccion:
            ws_act.append(["Estado", "Cantidad", "Con Informe de Cierre"])
            act = datos["graficos"]["actividades_estado"]
            for etiqueta, val in zip(act["etiquetas"], act["valores"]):
                ws_act.append([etiqueta, val, act["con_informe"] if etiqueta == "Finalizadas" else "-"])
            ws_act.append([])
        if "cobertura_lotes" in seleccion:
            ws_act.append(["Categoría", "Necesaria", "Mínima", "Adjudicada"])
            cob = datos["graficos"]["cobertura_lotes"]
            for i, cat in enumerate(cob["categorias"]):
                ws_act.append([cat, cob["necesaria"][i], cob["minima"][i], cob["adjudicada"][i]])
        _estilizar_cabecera(ws_act)
        _autoajustar_hoja(ws_act)

    # 5. Tiempos Bonita
    if "tiempos_bonita" in seleccion:
        ws_bon = wb.create_sheet("Tiempos Bonita")
        ws_bon.append(["Etapa", "Promedio (h)", "Mínimo (h)", "Máximo (h)", "Cantidad"])
        for et in datos["graficos"]["tiempos_bonita"]["etapas"]:
            ws_bon.append([et["etapa"], et["promedio_horas"], et["min_horas"], et["max_horas"], et["cantidad"]])
        _estilizar_cabecera(ws_bon)
        _autoajustar_hoja(ws_bon)

    # 6. Emergencias (Tipo/Gravedad y Municipio)
    if "emergencias_tipo_gravedad" in seleccion or "emergencias_municipio" in seleccion:
        ws_em = wb.create_sheet("Emergencias")
        if "emergencias_tipo_gravedad" in seleccion:
            tg = datos["graficos"]["emergencias_tipo_gravedad"]
            ws_em.append(["Tipo de Desastre", *tg["niveles"]])
            for i, tipo in enumerate(tg["tipos"]):
                ws_em.append([tipo, *[tg["series"][n][i] for n in tg["niveles"]]])
            ws_em.append([])
        if "emergencias_municipio" in seleccion:
            ws_em.append(["Municipio", "Cantidad Emergencias"])
            for muni in datos["graficos"]["emergencias_municipio"]:
                ws_em.append([muni["municipio"], muni["cantidad"]])
        _estilizar_cabecera(ws_em)
        _autoajustar_hoja(ws_em)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"reporte_auditor_{_fecha_tag()}.xlsx",
    )


def _decode_data_url(data_url: str) -> bytes | None:
    if not data_url or "," not in data_url:
        return None
    _, b64 = data_url.split(",", 1)
    try:
        return base64.b64decode(b64)
    except (ValueError, TypeError):
        return None


@auditor_bp.post("/reportes/export/pptx")
@login_required
@roles_required(RolEnum.AUDITOR)
def export_pptx():
    body = request.get_json(silent=True) or {}
    filtros = _filtros_desde_request(body.get("filtros") or {})
    imagenes = body.get("imagenes") or []
    datos = obtener_reporte_auditor(filtros)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Slide 1: Portada con diseño y título centrado
    slide_portada = prs.slides.add_slide(blank_layout)
    banda = slide_portada.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.35)
    )
    banda.fill.solid()
    banda.fill.fore_color.rgb = RGBColor(49, 46, 129)
    banda.line.fill.background()

    tb = slide_portada.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(11.333), Inches(3.8))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    p0 = tf.paragraphs[0]
    p0.text = "Informe Ejecutivo de Gestión de Emergencias"
    p0.alignment = PP_ALIGN.CENTER
    p0.font.size = Pt(38)
    p0.font.bold = True
    p0.font.color.rgb = RGBColor(30, 27, 75)

    p_sub = tf.add_paragraph()
    p_sub.text = "Panel de Estadísticas e Indicadores — Dirección / Auditoría"
    p_sub.alignment = PP_ALIGN.CENTER
    p_sub.font.size = Pt(18)
    p_sub.font.color.rgb = RGBColor(79, 70, 229)
    p_sub.space_before = Pt(12)

    p1 = tf.add_paragraph()
    p1.text = f"Generado: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}  |  Usuario: {current_user.nombre}"
    p1.alignment = PP_ALIGN.CENTER
    p1.font.size = Pt(14)
    p1.font.color.rgb = RGBColor(71, 85, 105)
    p1.space_before = Pt(24)

    filtros_txt = ", ".join(f"{k}={v}" for k, v in datos["filtros_aplicados"].items() if v) or "Sin filtros (histórico completo)"
    p2 = tf.add_paragraph()
    p2.text = f"Filtros aplicados: {filtros_txt}"
    p2.alignment = PP_ALIGN.CENTER
    p2.font.size = Pt(13)
    p2.font.color.rgb = RGBColor(100, 116, 139)
    p2.space_before = Pt(8)

    # Slide 2: Resumen KPIs
    slide_kpi = prs.slides.add_slide(blank_layout)
    title_kpi = slide_kpi.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.8))
    p_tk = title_kpi.text_frame.paragraphs[0]
    p_tk.text = "Resumen Ejecutivo de Indicadores (KPIs)"
    p_tk.font.size = Pt(24)
    p_tk.font.bold = True
    p_tk.font.color.rgb = RGBColor(30, 27, 75)

    kpi_items = [
        ("Emergencias Totales", str(datos["kpis"]["total_emergencias"])),
        ("Emergencias Activas / Cerradas", f"{datos['kpis']['emergencias_activas']} / {datos['kpis']['emergencias_cerradas']}"),
        ("Suministros Movilizados", str(datos["kpis"]["total_suministros"])),
        ("Resolución por Consorcios", f"{datos['kpis']['pct_consorcios']}% ({datos['kpis']['ofertas_consorcio']}/{datos['kpis']['ofertas_adjudicadas']})"),
        ("Actividades Finalizadas", f"{datos['kpis']['tasa_finalizacion_actividades']}% ({datos['kpis']['actividades_finalizadas']}/{datos['kpis']['total_actividades']})"),
        ("Duración Promedio Actividad", f"{datos['kpis']['promedio_dias_actividad']} días"),
    ]
    tabla_shape = slide_kpi.shapes.add_table(len(kpi_items) + 1, 2, Inches(0.8), Inches(1.4), Inches(11.7), Inches(4.8))
    tabla = tabla_shape.table
    tabla.cell(0, 0).text = "Indicador"
    tabla.cell(0, 1).text = "Valor"
    for idx, (label, val) in enumerate(kpi_items, start=1):
        tabla.cell(idx, 0).text = label
        tabla.cell(idx, 1).text = val

    # Slides 3..N: 1 Gráfico por slide con título explícito arriba (solo los visibles en la vista actual)
    for item in imagenes:
        img_bytes = _decode_data_url(item.get("data_url", ""))
        if not img_bytes:
            continue
        titulo_grafico = (item.get("titulo") or "").strip() or "Gráfico Estadístico"
        descripcion_grafico = (item.get("descripcion") or "").strip()

        slide = prs.slides.add_slide(blank_layout)
        hdr = slide.shapes.add_textbox(Inches(0.7), Inches(0.35), Inches(11.9), Inches(1.0))
        htf = hdr.text_frame
        htf.word_wrap = True
        hp = htf.paragraphs[0]
        hp.text = titulo_grafico
        hp.font.size = Pt(22)
        hp.font.bold = True
        hp.font.color.rgb = RGBColor(30, 27, 75)

        if descripcion_grafico:
            sp = htf.add_paragraph()
            sp.text = descripcion_grafico
            sp.font.size = Pt(12)
            sp.font.color.rgb = RGBColor(100, 116, 139)

        slide.shapes.add_picture(io.BytesIO(img_bytes), Inches(1.0), Inches(1.45), width=Inches(11.3), height=Inches(5.6))

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=f"reporte_auditor_{_fecha_tag()}.pptx",
    )
