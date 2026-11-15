"""Pruebas de métricas Bonita, RBAC y exportaciones (CSV/XLSX/JSON/PPTX) para Auditor."""
import base64
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask
from flask_login import LoginManager
from openpyxl import load_workbook
from pptx import Presentation

from src.core.enums import RolEnum
from src.core.services.bonita import BonitaError
from src.core.services.reportes import _BONITA_CACHE, obtener_metricas_bonita
from src.web.controllers.auditor import auditor_bp

SAMPLE_REPORT = {
    "filtros_aplicados": {
        "fecha_desde": "2026-01-01",
        "fecha_hasta": "2026-12-31",
        "tipo_desastre": "",
        "nivel_gravedad": "",
        "municipio_id": "",
    },
    "opciones_filtro": {
        "tipos_desastre": ["Hidrológico"],
        "niveles_gravedad": [{"valor": 3, "etiqueta": "Alto"}],
        "municipios": [{"id": 1, "nombre": "La Plata (Buenos Aires)"}],
    },
    "kpis": {
        "total_emergencias": 6,
        "emergencias_activas": 2,
        "emergencias_cerradas": 4,
        "total_suministros": 4083,
        "ofertas_adjudicadas": 6,
        "ofertas_consorcio": 4,
        "pct_consorcios": 66.7,
        "total_actividades": 8,
        "actividades_finalizadas": 6,
        "actividades_en_ejecucion": 2,
        "tasa_finalizacion_actividades": 75.0,
        "actividades_con_informe": 6,
        "promedio_dias_actividad": 8.2,
    },
    "graficos": {
        "suministros_mensuales": {
            "meses": ["2026-07", "2026-08"],
            "categorias": ["Personal", "Insumo", "Vehículo", "Equipamiento"],
            "series": {
                "Personal": [10, 8],
                "Insumo": [1200, 900],
                "Vehículo": [3, 0],
                "Equipamiento": [4, 5],
            },
        },
        "top_recursos": [{"nombre": "Raciones de Alimento Seco", "unidad": "Raciones", "cantidad": 2100}],
        "consorcios": {"etiquetas": ["Consorcio (Conjunta)", "Individual"], "valores": [4, 2], "porcentaje_consorcio": 66.7},
        "actividades_estado": {"etiquetas": ["Finalizadas", "En Ejecución"], "valores": [6, 2], "con_informe": 6},
        "cobertura_lotes": {
            "categorias": ["Personal", "Insumo", "Vehículo", "Equipamiento"],
            "necesaria": [30, 4200, 5, 13],
            "minima": [19, 2600, 3, 7],
            "adjudicada": [26, 4050, 5, 12],
        },
        "tiempos_bonita": {
            "bonita_disponible": True,
            "casos_consultados": 1,
            "etapas": [{"etapa": "Publicar convocatoria", "promedio_horas": 4.5, "min_horas": 4.5, "max_horas": 4.5, "cantidad": 1}],
        },
        "emergencias_tipo_gravedad": {
            "tipos": ["Hidrológico"],
            "niveles": ["Bajo", "Medio", "Alto", "Crítico"],
            "series": {"Bajo": [0], "Medio": [0], "Alto": [2], "Crítico": [0]},
        },
        "emergencias_municipio": [{"municipio": "La Plata (Buenos Aires)", "cantidad": 2}],
    },
}

# PNG 1x1 válido en base64 para probar inserción en PPTX
PNG_1X1_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)


class BonitaMetricasTests(unittest.TestCase):
    def setUp(self):
        _BONITA_CACHE.clear()

    def test_calcula_promedio_horas_por_etapa(self):
        cliente_mock = Mock()
        cliente_mock.listar_tareas_archivadas_caso.return_value = [
            {
                "name": "Publicar convocatoria",
                "reached_state_date": "2026-10-01 10:00:00.000",
                "archivedDate": "2026-10-01 12:30:00.000",
            },
            {
                "name": "Validar ofertas",
                "reached_state_date": "2026-10-01 13:00:00.000",
                "archivedDate": "2026-10-01 14:00:00.000",
            },
        ]
        emergencias = [SimpleNamespace(bonita_case_id=101)]
        res = obtener_metricas_bonita(emergencias, cliente_factory=lambda: cliente_mock)
        self.assertTrue(res["bonita_disponible"])
        self.assertEqual(res["casos_consultados"], 1)
        self.assertEqual(res["etapas"][0]["etapa"], "Publicar convocatoria")
        self.assertEqual(res["etapas"][0]["promedio_horas"], 2.5)
        self.assertEqual(res["etapas"][1]["etapa"], "Validar ofertas")
        self.assertEqual(res["etapas"][1]["promedio_horas"], 1.0)

    def test_degrada_si_bonita_falla(self):
        def factory_fallo():
            raise BonitaError("Connection refused")

        emergencias = [SimpleNamespace(bonita_case_id=202)]
        res = obtener_metricas_bonita(emergencias, cliente_factory=factory_fallo)
        self.assertFalse(res["bonita_disponible"])
        self.assertEqual(res["etapas"], [])


class AuditorExportsTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"
        self.app.register_blueprint(auditor_bp)
        login_manager = LoginManager(self.app)

        self.user_rol = RolEnum.AUDITOR

        @login_manager.user_loader
        def load_user(uid):
            return SimpleNamespace(id=int(uid), nombre="Auditor Test", rol=self.user_rol, is_authenticated=True, is_active=True, is_anonymous=False, get_id=lambda: str(uid))

        @self.app.get("/login-test")
        def login_test():
            from flask_login import login_user
            user = SimpleNamespace(id=1, nombre="Auditor Test", rol=self.user_rol, is_authenticated=True, is_active=True, is_anonymous=False, get_id=lambda: "1")
            login_user(user)
            return "ok"

        self.client = self.app.test_client()
        self.client.get("/login-test")

    def test_rbac_rechaza_otro_rol(self):
        self.user_rol = RolEnum.ONG
        res = self.client.get("/auditor/reportes/data")
        self.assertEqual(res.status_code, 403)

    @patch("src.web.controllers.auditor.obtener_reporte_auditor", return_value=SAMPLE_REPORT)
    def test_export_json_y_csv(self, _mock_rep):
        res_json = self.client.get("/auditor/reportes/export/json")
        self.assertEqual(res_json.status_code, 200)
        self.assertIn("attachment;", res_json.headers.get("Content-Disposition", ""))
        parsed = json.loads(res_json.data.decode("utf-8"))
        self.assertEqual(parsed["kpis"]["total_suministros"], 4083)

        res_csv = self.client.get("/auditor/reportes/export/csv")
        self.assertEqual(res_csv.status_code, 200)
        texto_csv = res_csv.data.decode("utf-8-sig")
        self.assertIn("Suministros Mensuales", texto_csv)
        self.assertIn("Publicar convocatoria", texto_csv)

    @patch("src.web.controllers.auditor.obtener_reporte_auditor", return_value=SAMPLE_REPORT)
    def test_export_xlsx_multihoja(self, _mock_rep):
        res = self.client.get("/auditor/reportes/export/xlsx")
        self.assertEqual(res.status_code, 200)
        wb = load_workbook(io.BytesIO(res.data))
        self.assertEqual(wb.sheetnames, ["Resumen KPIs", "Suministros", "Consorcios", "Actividades", "Tiempos Bonita", "Emergencias"])
        self.assertGreater(wb["Suministros"].max_row, 2)

    @patch("src.web.controllers.auditor.obtener_reporte_auditor", return_value=SAMPLE_REPORT)
    def test_export_pptx_incluye_titulo_en_cada_grafico(self, _mock_rep):
        payload = {
            "filtros": {"tipo_desastre": "Hidrológico"},
            "imagenes": [
                {"id": "c1", "titulo": "Suministros Movilizados por Mes", "descripcion": "Filtro aplicado", "data_url": PNG_1X1_DATA_URL},
                {"id": "c2", "titulo": "Resolución por Consorcios de ONGs", "descripcion": "Porcentaje", "data_url": PNG_1X1_DATA_URL},
            ],
        }
        res = self.client.post("/auditor/reportes/export/pptx", json=payload)
        self.assertEqual(res.status_code, 200)
        prs = Presentation(io.BytesIO(res.data))
        # Portada + KPIs + 2 gráficos = 4 slides
        self.assertEqual(len(prs.slides), 4)

        for slide, esperado in zip(list(prs.slides)[2:], ["Suministros Movilizados por Mes", "Resolución por Consorcios de ONGs"]):
            textos = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
            imagenes = [sh for sh in slide.shapes if sh.shape_type == 13]  # PICTURE
            self.assertTrue(any(esperado in t for t in textos), f"Falta título '{esperado}' en slide")
            self.assertEqual(len(imagenes), 1)

        # Verificar portada centrada
        from pptx.enum.text import PP_ALIGN
        portada_textboxes = [sh for sh in prs.slides[0].shapes if sh.has_text_frame]
        self.assertTrue(any(p.alignment == PP_ALIGN.CENTER for sh in portada_textboxes for p in sh.text_frame.paragraphs))

    @patch("src.web.controllers.auditor.obtener_reporte_auditor", return_value=SAMPLE_REPORT)
    def test_export_filtra_graficos_visibles(self, _mock_rep):
        res_json = self.client.get("/auditor/reportes/export/json?graficos=consorcios")
        parsed = json.loads(res_json.data.decode("utf-8"))
        self.assertEqual(list(parsed["graficos"].keys()), ["consorcios"])

        res_xlsx = self.client.get("/auditor/reportes/export/xlsx?graficos=consorcios")
        wb = load_workbook(io.BytesIO(res_xlsx.data))
        self.assertEqual(wb.sheetnames, ["Resumen KPIs", "Consorcios"])
