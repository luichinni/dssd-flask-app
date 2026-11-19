"""Pruebas del callback de validación externa desde Bonita y registro de ofertas."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from src.core.enums import EstadoOfertaEnum
from src.core.services.ofertas import registrar_ofertas_validadas
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


if __name__ == "__main__":
    unittest.main()
