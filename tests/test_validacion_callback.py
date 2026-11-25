"""Pruebas del callback de validación externa desde Bonita y registro de ofertas."""
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

from src.core.enums import AccionPostOfertaEnum, EstadoOfertaEnum, TipoDesastreEnum
from src.core.services import bonita as bonita_service
from src.core.services.lotes import continuar_con_ofertas_disponibles, reabrir_convocatoria, reformular_lote
from src.core.services.ofertas import (
    detalles_para_convocatoria,
    registrar_compromiso_externo,
    registrar_liberacion_externa,
    registrar_ofertas_validadas,
)
from src.core.timezone import ahora_ar
from src.web.controllers.bonita_callbacks import bonita_callbacks_bp


class TestValidacionCallback(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["BONITA_CALLBACK_API_KEY"] = "clave_best_api_ever"
        self.app.register_blueprint(bonita_callbacks_bp)
        self.client = self.app.test_client()

    def test_callback_rechaza_api_key_invalida(self):
        resp = self.client.post("/api/emergencias/1/ofertas-validadas", json={"ofertas_validadas": []})
        self.assertEqual(resp.status_code, 401)

    @patch("src.web.controllers.bonita_callbacks.registrar_ofertas_validadas")
    def test_callback_acepta_y_registra_ofertas(self, mock_registrar):
        payload = {"id_emergencia": 1, "estado_general": "validado", "ofertas_validadas": [{"id_oferta": 10}]}
        resp = self.client.post(
            "/api/emergencias/1/ofertas-validadas",
            json=payload,
            headers={"secret-key-api": "clave_best_api_ever"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"ok": True})
        mock_registrar.assert_called_once_with(1, payload)

    @patch("src.core.services.ofertas.db")
    @patch("src.core.services.ofertas.LoteNecesidades")
    @patch("src.core.services.ofertas.Oferta")
    def test_registrar_ofertas_validadas_actualiza_estados(self, mock_oferta_cls, mock_lote_cls, mock_db):
        mock_db.session.get.return_value = SimpleNamespace(id=1)

        ver_valida = SimpleNamespace(numero_version=1, estado_version="Pendiente", observaciones=None)
        oferta_valida = SimpleNamespace(
            id=10,
            estado=EstadoOfertaEnum.PENDIENTE,
            version_actual=1,
            versiones=[ver_valida],
            participaciones=[SimpleNamespace(estado=EstadoOfertaEnum.PENDIENTE.value)],
            fecha_ultima_modificacion=None,
        )
        ver_invalida = SimpleNamespace(numero_version=1, estado_version="Pendiente", observaciones=None)
        oferta_invalida = SimpleNamespace(
            id=11,
            estado=EstadoOfertaEnum.PENDIENTE,
            version_actual=1,
            versiones=[ver_invalida],
            participaciones=[SimpleNamespace(estado=EstadoOfertaEnum.PENDIENTE.value)],
            fecha_ultima_modificacion=None,
        )
        lote = SimpleNamespace(id=5, bonita_estado="validando")

        mock_oferta_cls.query.filter_by.return_value.all.return_value = [oferta_valida, oferta_invalida]
        mock_lote_cls.query.filter_by.return_value.all.return_value = [lote]

        registrar_ofertas_validadas(
            1,
            {
                "id_emergencia": 1,
                "ofertas_validadas": [
                    {
                        "id_oferta": 10,
                        "perfil_competencia_ong": "Avanzado",
                        "nivel_riesgo_permitido": "Alto",
                    }
                ],
            },
        )

        self.assertEqual(oferta_valida.estado, EstadoOfertaEnum.ACEPTADA)
        self.assertEqual(oferta_valida.participaciones[0].estado, EstadoOfertaEnum.ACEPTADA.value)
        self.assertEqual(ver_valida.estado_version, EstadoOfertaEnum.ACEPTADA.value)
        self.assertEqual(oferta_invalida.estado, EstadoOfertaEnum.RECHAZADA)
        self.assertEqual(oferta_invalida.participaciones[0].estado, EstadoOfertaEnum.RECHAZADA.value)
        self.assertEqual(ver_invalida.estado_version, EstadoOfertaEnum.RECHAZADA.value)
        self.assertEqual(lote.bonita_estado, "validado")
        mock_db.session.commit.assert_called_once()

    def test_solicitud_validacion_rechaza_api_key_invalida(self):
        resp = self.client.get("/api/emergencias/1/solicitud-validacion")
        self.assertEqual(resp.status_code, 401)

    @patch("src.web.controllers.bonita_callbacks.construir_solicitud_validacion")
    def test_solicitud_validacion_devuelve_payload(self, mock_construir):
        esperado = {"id_emergencia": 1, "tipo_desastre": "hidrologico", "gravedad": "alto", "ofertas": []}
        mock_construir.return_value = esperado
        resp = self.client.get(
            "/api/emergencias/1/solicitud-validacion",
            headers={"secret-key-api": "clave_best_api_ever"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), esperado)
        mock_construir.assert_called_once_with(1)

    @patch("src.core.database.db")
    @patch("src.core.models.lote_necesidades.LoteNecesidades")
    @patch("src.core.services.ofertas.detalles_para_convocatoria")
    @patch("src.core.models.oferta.Oferta")
    @patch("src.core.models.emergencia.Emergencia")
    def test_construir_solicitud_validacion_marca_validando(
        self, mock_emergencia_cls, mock_oferta_cls, mock_detalles, mock_lote_cls, mock_db
    ):
        mock_db.session.get.return_value = SimpleNamespace(
            id=1,
            tipo_desastre=TipoDesastreEnum.hidrologico,
            nivel_gravedad=3,
        )
        oferta = SimpleNamespace(id=10, es_conjunta=False, creada_por_ong_id=2, participaciones=[])
        mock_oferta_cls.query.filter.return_value.filter.return_value.all.return_value = [oferta]
        mock_detalles.return_value = [SimpleNamespace(id_recurso=7, cantidad=15)]
        lote = SimpleNamespace(id=5, bonita_estado="sincronizado")
        mock_lote_cls.query.filter_by.return_value.all.return_value = [lote]

        payload = bonita_service.construir_solicitud_validacion(1)
        self.assertEqual(payload["id_emergencia"], 1)
        self.assertEqual(payload["tipo_desastre"], "hidrologico")
        self.assertEqual(payload["gravedad"], "alto")
        self.assertEqual(
            payload["ofertas"],
            [{"id_oferta": 10, "es_conjunta": False, "id_ong": 2, "recursos": [{"id_recurso": 7, "cantidad_ofrecida": 15}]}],
        )
        self.assertEqual(lote.bonita_estado, "validando")
        mock_db.session.commit.assert_called_once()

    @patch("src.core.services.lotes._notificar_convocatoria")
    @patch("src.core.services.lotes.completar_decision_post_convocatoria")
    @patch("src.core.services.lotes.db")
    @patch("src.core.services.lotes._validar_decision_pendiente")
    def test_reabrir_resetea_bonita_estado_a_sincronizado(self, mock_validar, mock_db, mock_bonita, mock_notif):
        lote = SimpleNamespace(
            id=9, bonita_estado="validado", emergencia=SimpleNamespace(bonita_case_id=77)
        )
        mock_validar.return_value = lote
        cierre = ahora_ar() + timedelta(hours=24)

        reabrir_convocatoria(9, cierre)

        self.assertEqual(lote.bonita_estado, "sincronizado")
        mock_bonita.assert_called_once_with(77, AccionPostOfertaEnum.REABRIR, cierre)
        mock_db.session.commit.assert_called_once()
        mock_notif.assert_called_once_with(lote, reabierta=True)

    @patch("src.core.services.lotes._notificar_convocatoria")
    @patch("src.core.services.lotes.completar_decision_post_convocatoria", side_effect=bonita_service.BonitaError("HTTP 401"))
    @patch("src.core.services.lotes.db")
    @patch("src.core.services.lotes._validar_decision_pendiente")
    def test_fallo_en_bonita_revierte_reapertura(self, mock_validar, mock_db, mock_bonita, mock_notif):
        mock_validar.return_value = SimpleNamespace(emergencia=SimpleNamespace(bonita_case_id=77))

        with self.assertRaises(bonita_service.BonitaError):
            reabrir_convocatoria(9, ahora_ar() + timedelta(hours=24))

        mock_db.session.rollback.assert_called_once()
        mock_db.session.commit.assert_not_called()
        mock_notif.assert_not_called()

    @patch("src.core.services.lotes._notificar_convocatoria")
    @patch("src.core.services.lotes.completar_decision_post_convocatoria")
    @patch("src.core.services.lotes.db")
    @patch("src.core.services.lotes._validar_decision_pendiente")
    def test_reformular_reemplaza_recursos_y_conserva_el_historial_de_la_oferta(
        self, mock_validar, mock_db, mock_bonita, mock_notif,
    ):
        recurso = Mock()
        mock_db.session.get.return_value = recurso
        lote = SimpleNamespace(detalles=[SimpleNamespace(id_recurso=5)], emergencia=SimpleNamespace(bonita_case_id=77))
        mock_validar.return_value = lote
        cierre = ahora_ar() + timedelta(hours=24)
        anteriores = [SimpleNamespace(id_recurso=5), SimpleNamespace(id_recurso=6)]
        oferta = SimpleNamespace(
            version_actual=1,
            versiones=[SimpleNamespace(numero_version=1, detalles=anteriores)],
            convocatoria=lote,
        )

        with patch("src.core.services.lotes.LoteDetalle", return_value=SimpleNamespace(id_recurso=6)) as detalle:
            reformular_lote(9, [{"recurso_id": 6, "cantidad_necesaria": 4, "min_r": 2}], cierre)

        detalle.assert_called_once_with(recurso=recurso, cantidad_necesaria=4, cantidad_minima=2)
        self.assertEqual(detalles_para_convocatoria(oferta), [anteriores[1]])
        self.assertEqual(len(anteriores), 2)
        mock_bonita.assert_called_once_with(77, AccionPostOfertaEnum.REFORMULAR, cierre)
        mock_notif.assert_called_once_with(lote, reabierta=True)

    @patch("src.core.services.lotes.completar_decision_post_convocatoria")
    @patch("src.core.services.lotes.db")
    @patch("src.core.services.lotes.Oferta")
    @patch("src.core.services.lotes._validar_decision_pendiente")
    def test_continuar_requiere_ofertas_validadas(self, mock_validar, mock_oferta, mock_db, mock_bonita):
        lote = SimpleNamespace(
            emergencia_id=1, bonita_estado="validado", emergencia=SimpleNamespace(bonita_case_id=77)
        )
        mock_validar.return_value = lote
        consulta = mock_oferta.query.filter_by.return_value
        consulta.first.return_value = None

        with self.assertRaises(ValueError):
            continuar_con_ofertas_disponibles(9)
        mock_bonita.assert_not_called()

        consulta.first.return_value = SimpleNamespace(id=10)
        continuar_con_ofertas_disponibles(9)

        mock_oferta.query.filter_by.assert_called_with(id_emergencia=1, estado=EstadoOfertaEnum.ACEPTADA)
        mock_bonita.assert_called_once_with(77, AccionPostOfertaEnum.CONTINUAR, None)
        mock_db.session.commit.assert_called_once()
        self.assertEqual(lote.bonita_estado, "cobertura_parcial")

    def test_compromiso_registrado_rechaza_api_key_invalida(self):
        resp = self.client.post("/api/emergencias/1/compromiso-registrado", json={})
        self.assertEqual(resp.status_code, 401)

    @patch("src.web.controllers.bonita_callbacks.registrar_compromiso_externo")
    def test_compromiso_registrado_acepta_callback(self, mock_registrar):
        payload = {"id_emergencia": 1, "estado": "bloqueo_exitoso", "ofertas_rechazadas": []}
        resp = self.client.post(
            "/api/emergencias/1/compromiso-registrado",
            json=payload,
            headers={"secret-key-api": "clave_best_api_ever"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"ok": True})
        mock_registrar.assert_called_once_with(1, payload)

    @patch("src.web.controllers.bonita_callbacks.registrar_liberacion_externa")
    def test_recursos_liberados_acepta_callback(self, mock_registrar):
        payload = {"estado": "liberacion_exitosa", "id_ong": 1}
        resp = self.client.post(
            "/api/emergencias/1/recursos-liberados",
            json=payload,
            headers={"secret-key-api": "clave_best_api_ever"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"ok": True})
        mock_registrar.assert_called_once_with(1, payload)

    @patch("src.core.services.ofertas.ActividadONG")
    @patch("src.core.services.ofertas.Oferta")
    @patch("src.core.services.ofertas.db")
    def test_registrar_compromiso_externo_actualiza_rechazos_y_estado(self, mock_db, mock_oferta_cls, mock_act_cls):
        em = SimpleNamespace(id=1, bonita_estado="vinculada")
        mock_db.session.get.return_value = em
        ver = SimpleNamespace(numero_version=1, estado_version="Aceptada", observaciones=None)
        oferta_rech = SimpleNamespace(
            id=20,
            estado=EstadoOfertaEnum.ADJUDICADA,
            version_actual=1,
            versiones=[ver],
            participaciones=[SimpleNamespace(estado="Aceptada")],
            fecha_ultima_modificacion=None,
        )
        mock_oferta_cls.query.filter.return_value.all.return_value = [oferta_rech]

        registrar_compromiso_externo(1, {"ofertas_rechazadas": [{"id_oferta": 20}]})
        self.assertEqual(em.bonita_estado, "comprometida")
        self.assertEqual(oferta_rech.estado, EstadoOfertaEnum.RECHAZADA)
        self.assertEqual(ver.estado_version, EstadoOfertaEnum.RECHAZADA.value)
        mock_act_cls.query.filter.return_value.delete.assert_called_once()
        mock_db.session.commit.assert_called_once()

    @patch("src.core.services.ofertas.ActividadONG")
    @patch("src.core.services.ofertas.db")
    def test_registrar_liberacion_externa_finaliza_emergencia(self, mock_db, mock_act_cls):
        em = SimpleNamespace(id=1, bonita_estado="comprometida", lotes=[SimpleNamespace(id=7)])
        mock_db.session.get.return_value = em
        mock_act_cls.query.filter.return_value.count.return_value = 0

        registrar_liberacion_externa(1, {"estado": "liberacion_exitosa"})
        self.assertEqual(em.bonita_estado, "finalizada")
        mock_db.session.commit.assert_called_once()


class TestVigilanteReintentosBonita(unittest.TestCase):
    def setUp(self):
        bonita_service._REINTENTOS_ACTIVIDAD.clear()
        self.app = Flask(__name__)
        self.app.config["BONITA_ADMIN_USERNAME"] = "walter.bates"
        self.app.config["BONITA_ADMIN_PASSWORD"] = "bpm"

    def test_reintenta_actividad_fallida_y_luego_marca_agotada(self):
        cliente = Mock()
        cliente.pedir.side_effect = [
            [{"id": "901", "name": "Validar ofertas", "caseId": "77", "state": "failed"}],
            None,
            [{"id": "901", "name": "Validar ofertas", "caseId": "77", "state": "failed"}],
        ]
        lote = SimpleNamespace(id=9, bonita_estado="validando")

        with (
            self.app.app_context(),
            patch("src.core.services.bonita._ClienteBonita", return_value=cliente),
            patch("src.core.models.emergencia.Emergencia") as mock_em,
            patch("src.core.models.lote_necesidades.LoteNecesidades") as mock_lote,
            patch("src.core.database.db") as mock_db,
        ):
            mock_em.query.filter_by.return_value.first.return_value = SimpleNamespace(id=3)
            mock_lote.query.filter_by.return_value.all.return_value = [lote]

            res1 = bonita_service.reintentar_actividades_fallidas(max_intentos=1)
            self.assertEqual(res1, {"reintentadas": 1, "agotadas": 0})
            cliente.pedir.assert_any_call("/API/bpm/activity/901", "PUT", {"state": "replay"}, "reintentar actividad Validar ofertas")

            res2 = bonita_service.reintentar_actividades_fallidas(max_intentos=1)
            self.assertEqual(res2, {"reintentadas": 0, "agotadas": 1})
            self.assertEqual(lote.bonita_estado, "fallo_validacion")
            mock_db.session.commit.assert_called_once()

    def test_no_actua_cuando_no_hay_actividades_fallidas(self):
        cliente = Mock()
        cliente.pedir.return_value = []
        with self.app.app_context(), patch("src.core.services.bonita._ClienteBonita", return_value=cliente):
            res = bonita_service.reintentar_actividades_fallidas(max_intentos=5)
        self.assertEqual(res, {"reintentadas": 0, "agotadas": 0})
        cliente.pedir.assert_called_once_with("/API/bpm/activity?p=0&c=100&f=state%3Dfailed", etapa="consultar actividades fallidas")


if __name__ == "__main__":
    unittest.main()
