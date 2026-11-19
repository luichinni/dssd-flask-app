"""Pruebas de ejecución de tareas sin conectarse a Bonita."""
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.core.services.bonita import BonitaError, _ClienteBonita, completar_publicacion_lote, iniciar_proceso


class TareasBonitaTests(unittest.TestCase):
    def cliente(self):
        cliente = object.__new__(_ClienteBonita)
        cliente.timeout = 0.01
        cliente.pedir = Mock()
        return cliente

    def test_filtra_tareas_de_otro_caso(self):
        c = self.cliente()
        c.pedir.return_value = [
            {"id": "1", "caseId": "1003"},
            {"id": "2", "caseId": "9999"},
        ]
        self.assertEqual(c.tareas(1003), [{"id": "1", "caseId": "1003"}])

    def test_asigna_y_ejecuta_con_contrato(self):
        c = self.cliente()
        c.tareas = Mock(return_value=[{"id": "42", "name": "Registrar emergencia", "state": "ready", "assigned_id": ""}])
        c.pedir.side_effect = [{"user_id": "4"}, None, None]
        c.completar(1003, "Registrar emergencia", {"id_emergencia_input": 8})
        calls = c.pedir.call_args_list
        self.assertEqual(calls[1].args[:3], ("/API/bpm/humanTask/42", "PUT", {"assigned_id": 4}))
        self.assertEqual(calls[2].args[:3], ("/API/bpm/userTask/42/execution", "POST", {"id_emergencia_input": 8}))

    def test_no_reasigna_tarea_de_otra_persona(self):
        c = self.cliente()
        c.tareas = Mock(return_value=[{"id": "42", "name": "Publicar convocatoria", "state": "ready", "assigned_id": "5"}])
        c.pedir.return_value = {"user_id": "4"}
        with self.assertRaises(BonitaError):
            c.completar(1003, "Publicar convocatoria")
        self.assertEqual(c.pedir.call_count, 1)

    def test_omite_tarea_completada(self):
        c = self.cliente()
        c.tareas = Mock(side_effect=[[], [{"name": "Crear lotes de necesidades", "state": "completed"}]])
        c.completar(1003, "Crear lotes de necesidades")
        c.pedir.assert_not_called()

    def test_esperar_nueva_ignora_archivada_anterior(self):
        c = self.cliente()
        c.timeout = 0.6
        c.tareas = Mock(side_effect=[
            [],
            [{"name": "Publicar convocatoria", "state": "completed"}],
            [{"id": "88", "name": "Publicar convocatoria", "state": "ready", "assigned_id": ""}],
        ])
        c.pedir.side_effect = [{"user_id": "4"}, None, None]
        c.completar(1003, "Publicar convocatoria", {"fecha_cierre_input": "2026-11-19T14:00:00.000-03:00"}, esperar_nueva=True)
        calls = c.pedir.call_args_list
        self.assertEqual(calls[1].args[:3], ("/API/bpm/humanTask/88", "PUT", {"assigned_id": 4}))
        self.assertEqual(calls[2].args[:3], ("/API/bpm/userTask/88/execution", "POST", {"fecha_cierre_input": "2026-11-19T14:00:00.000-03:00"}))

    def test_no_reintenta_ejecucion_ni_avanza_tras_fallo(self):
        municipio = Mock()
        coordinador = Mock()
        coordinador.completar.side_effect = BonitaError("HTTP 500")
        with patch("src.core.services.bonita._ClienteBonita", side_effect=[municipio, coordinador]) as cliente:
            fecha = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
            with self.assertRaises(BonitaError):
                completar_publicacion_lote(1003, 8, fecha)
        self.assertEqual([llamada.args for llamada in cliente.call_args_list], [(), ("CCR",)])
        municipio.completar.assert_called_once_with(1003, "Registrar emergencia", {"id_emergencia_input": 8})
        coordinador.completar.assert_called_once_with(1003, "Crear lotes de necesidades")


class ResolucionProcesoBonitaTests(unittest.TestCase):
    def test_resuelve_solo_definicion_habilitada_con_nombre_y_version_exactos(self):
        cliente = object.__new__(_ClienteBonita)
        cliente.pedir = Mock(return_value=[
            {"id": "7", "name": "BestRescueSyncEver", "version": "1.0", "activationState": "DISABLED"},
            {"id": "42", "name": "BestRescueSyncEver", "version": "1.0", "activationState": "ENABLED"},
            {"id": "99", "name": "Otro", "version": "1.0", "activationState": "ENABLED"},
        ])
        self.assertEqual(cliente.resolver_process_definition_id(), 42)
        self.assertIn("activationState%3DENABLED", cliente.pedir.call_args.args[0])

    def test_falla_si_no_hay_definicion_habilitada(self):
        cliente = object.__new__(_ClienteBonita)
        cliente.pedir = Mock(return_value=[])
        with self.assertRaises(BonitaError):
            cliente.resolver_process_definition_id()

    def test_actualiza_id_obsoleto_y_reintenta_una_vez(self):
        from flask import Flask
        cliente = Mock()
        cliente.resolver_process_definition_id.return_value = 52
        cliente.pedir.side_effect = [BonitaError("HTTP 404", status_code=404), {"caseId": "900"}]
        app = Flask(__name__)
        app.config["BONITA_PROCESS_ID"] = 42
        with app.app_context(), patch("src.core.services.bonita._ClienteBonita", return_value=cliente):
            self.assertEqual(iniciar_proceso({"id": 1}), 900)
        self.assertEqual(app.config["BONITA_PROCESS_ID"], 52)
        self.assertEqual(cliente.pedir.call_count, 2)

    def test_resuelve_si_el_arranque_no_dejo_id_en_cache(self):
        from flask import Flask
        cliente = Mock()
        cliente.resolver_process_definition_id.return_value = 53
        cliente.pedir.return_value = {"caseId": "901"}
        app = Flask(__name__)
        app.config["BONITA_PROCESS_ID"] = None
        with app.app_context(), patch("src.core.services.bonita._ClienteBonita", return_value=cliente):
            self.assertEqual(iniciar_proceso({"id": 2}), 901)
        cliente.resolver_process_definition_id.assert_called_once_with()
        self.assertEqual(app.config["BONITA_PROCESS_ID"], 53)
        self.assertEqual(cliente.pedir.call_args.args[0], "/API/bpm/process/53/instantiation")

    def test_no_reintenta_respuesta_ambigua(self):
        from flask import Flask
        cliente = Mock()
        cliente.pedir.side_effect = BonitaError("respuesta ambigua", status_code=500)
        app = Flask(__name__)
        app.config["BONITA_PROCESS_ID"] = 42
        with app.app_context(), patch("src.core.services.bonita._ClienteBonita", return_value=cliente):
            with self.assertRaises(BonitaError):
                iniciar_proceso({"id": 1})
        self.assertEqual(cliente.pedir.call_count, 1)
        cliente.resolver_process_definition_id.assert_not_called()


if __name__ == "__main__":
    unittest.main()
