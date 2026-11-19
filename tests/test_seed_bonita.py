"""Pruebas unitarias para el orquestador seed-bonita."""
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

from src.core.enums import EstadoActividadEnum
from src.core.services import seed_bonita
from src.core.services.bonita import BonitaError
from src.core.timezone import ahora_ar


class TestSeedBonita(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_falla_si_faltan_usuarios_base(self):
        with self.app.app_context(), patch("src.core.services.seed_bonita.Usuario") as mock_usr:
            mock_usr.query.filter_by.return_value.first.return_value = None
            with self.assertRaises(BonitaError):
                seed_bonita.ejecutar_seed_bonita(limite=1)

    @patch("src.core.services.seed_bonita._ClienteBonita")
    @patch("src.core.services.seed_bonita._asegurar_inventario_local", return_value={})
    @patch("src.core.services.seed_bonita._verificar_precondiciones")
    @patch("src.core.services.seed_bonita.Emergencia")
    @patch("src.core.services.seed_bonita.Municipio")
    @patch("src.core.services.seed_bonita.RecursoCatalogo")
    @patch("src.core.services.seed_bonita.db")
    @patch("src.core.services.seed_bonita.Usuario")
    def test_omite_escenarios_ya_archivados_en_bonita(
        self, mock_usr, mock_db, mock_rec, mock_muni, mock_em, mock_pre, mock_inv, mock_cli
    ):
        u_op = SimpleNamespace(id=1, datos_adicionales={})
        u_o1 = SimpleNamespace(id=2, datos_adicionales={"ong_id": 1})
        u_o2 = SimpleNamespace(id=3, datos_adicionales={"ong_id": 2})
        mock_usr.query.filter_by.return_value.first.side_effect = [u_op, u_o1, u_o2]
        mock_db.session.get.side_effect = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        mock_rec.query.all.return_value = [
            SimpleNamespace(id=i, nombre=n)
            for i, n in enumerate(
                [
                    "Paramédicos de Emergencia",
                    "Raciones de Alimento Seco",
                    "Ambulancia de Traslado 4x4",
                    "Carpas Sanitarias de Campaña",
                    "Kits de Higiene Comunitarios",
                ],
                start=1,
            )
        ]
        mock_muni.query.all.return_value = [SimpleNamespace(id=2, nombre="La Plata")]
        mock_em.query.filter_by.return_value.first.return_value = SimpleNamespace(
            id=99, bonita_estado="finalizada", bonita_case_id=555
        )
        cliente = Mock()
        cliente.obtener_caso_archivado.return_value = {"id": "555"}
        mock_cli.return_value = cliente

        with self.app.app_context():
            res = seed_bonita.ejecutar_seed_bonita(limite=1)

        self.assertEqual(res["creados"], [])
        self.assertEqual(len(res["omitidos"]), 1)
        self.assertEqual(res["omitidos"][0]["case_id"], 555)
        mock_pre.assert_called_once()

    @patch("src.core.services.seed_bonita.time.sleep")
    @patch("src.core.services.seed_bonita._esperar_caso_archivado", return_value={"id": "701"})
    @patch("src.core.services.seed_bonita.finalizar_actividad")
    @patch("src.core.services.seed_bonita.ActividadONG")
    @patch("src.core.services.seed_bonita.enviar_adjudicaciones_a_bonita")
    @patch("src.core.services.seed_bonita.adjudicar_oferta")
    @patch("src.core.services.seed_bonita.listar_ofertas_aceptadas")
    @patch("src.core.services.seed_bonita._esperar_tarea_lista")
    @patch("src.core.services.seed_bonita._esperar_validacion_lote")
    @patch("src.core.services.seed_bonita._crear_ofertas_escenario")
    @patch("src.core.services.seed_bonita.publicar_lote")
    @patch("src.core.services.seed_bonita.crear_emergencia")
    @patch("src.core.services.seed_bonita._limpiar_incompleto")
    @patch("src.core.services.seed_bonita._ClienteBonita")
    @patch("src.core.services.seed_bonita._asegurar_inventario_local", return_value={})
    @patch("src.core.services.seed_bonita._verificar_precondiciones")
    @patch("src.core.services.seed_bonita.Emergencia")
    @patch("src.core.services.seed_bonita.Municipio")
    @patch("src.core.services.seed_bonita.RecursoCatalogo")
    @patch("src.core.services.seed_bonita.db")
    @patch("src.core.services.seed_bonita.Usuario")
    def test_ejecuta_un_escenario_completo_con_mocks(
        self,
        mock_usr,
        mock_db,
        mock_rec,
        mock_muni,
        mock_em_cls,
        mock_pre,
        mock_inv,
        mock_cli,
        mock_limpiar,
        mock_crear_em,
        mock_pub_lote,
        mock_crear_of,
        mock_esp_val,
        mock_esp_tarea,
        mock_listar_ac,
        mock_adj,
        mock_env_adj,
        mock_act_cls,
        mock_fin_act,
        mock_esp_arch,
        mock_sleep,
    ):
        u_op = SimpleNamespace(id=1, datos_adicionales={})
        u_o1 = SimpleNamespace(id=2, datos_adicionales={"ong_id": 1})
        u_o2 = SimpleNamespace(id=3, datos_adicionales={"ong_id": 2})
        mock_usr.query.filter_by.return_value.first.side_effect = [u_op, u_o1, u_o2]

        em_obj = SimpleNamespace(id=50, bonita_case_id=701, bonita_estado="vinculada")
        mock_db.session.get.side_effect = [SimpleNamespace(id=1), SimpleNamespace(id=2), em_obj]
        mock_rec.query.all.return_value = [
            SimpleNamespace(id=i, nombre=n)
            for i, n in enumerate(
                [
                    "Paramédicos de Emergencia",
                    "Raciones de Alimento Seco",
                    "Ambulancia de Traslado 4x4",
                    "Carpas Sanitarias de Campaña",
                    "Kits de Higiene Comunitarios",
                ],
                start=1,
            )
        ]
        mock_muni.query.all.return_value = [SimpleNamespace(id=2, nombre="La Plata")]
        mock_em_cls.query.filter_by.return_value.first.return_value = None

        mock_crear_em.return_value = em_obj
        lote_obj = SimpleNamespace(
            id=80,
            bonita_estado="sincronizado",
            fecha_cierre_ofertas=ahora_ar() - timedelta(seconds=1),
        )
        mock_pub_lote.return_value = lote_obj
        mock_esp_val.return_value = SimpleNamespace(
            id=80,
            bonita_estado="validado",
            fecha_cierre_ofertas=ahora_ar() - timedelta(seconds=1),
        )
        mock_listar_ac.return_value = [SimpleNamespace(id=101)]
        mock_act_cls.query.filter_by.return_value.order_by.return_value.all.return_value = [
            SimpleNamespace(id=301, ong_id=1, estado=EstadoActividadEnum.EN_EJECUCION)
        ]

        with self.app.app_context():
            res = seed_bonita.ejecutar_seed_bonita(limite=1, ventana_segundos=1)

        self.assertEqual(len(res["creados"]), 1)
        self.assertEqual(res["creados"][0]["case_id"], 701)
        self.assertEqual(em_obj.bonita_estado, "finalizada")
        mock_adj.assert_called_once_with(101, emergencia_id=50)
        mock_env_adj.assert_called_once_with(50)
        mock_fin_act.assert_called_once()


if __name__ == "__main__":
    unittest.main()
