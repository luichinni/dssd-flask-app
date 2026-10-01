"""Pruebas de ejecución de tareas sin conectarse a Bonita."""
import unittest
from unittest.mock import Mock, patch

from src.core.services.bonita import BonitaError, _ClienteBonita, completar_publicacion_lote


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

    def test_no_reintenta_ejecucion_ni_avanza_tras_fallo(self):
        c = Mock()
        c.completar.side_effect = [None, BonitaError("HTTP 500")]
        with patch("src.core.services.bonita._ClienteBonita", return_value=c):
            with self.assertRaises(BonitaError):
                completar_publicacion_lote(1003, 8)
        self.assertEqual(c.completar.call_count, 2)
        self.assertEqual(c.completar.call_args_list[-1].args[1], "Crear lotes de necesidades")


if __name__ == "__main__":
    unittest.main()
