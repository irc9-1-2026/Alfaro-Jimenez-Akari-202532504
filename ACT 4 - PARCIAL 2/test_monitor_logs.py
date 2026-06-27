import unittest
from monitor_logs import contar_por_nivel, detectar_fuerza_bruta


class TestConteoDeNiveles(unittest.TestCase):
    """Pruebas para la función contar_por_nivel."""

    def setUp(self):
        # Conjunto de eventos de prueba — no modificar
        self.eventos = [
            {"nivel": "ERROR",   "mensaje": "Intento de login fallido desde 10.0.0.1"},
            {"nivel": "ERROR",   "mensaje": "Intento de login fallido desde 10.0.0.1"},
            {"nivel": "ERROR",   "mensaje": "Intento de login fallido desde 10.0.0.1"},
            {"nivel": "WARNING", "mensaje": "Memoria alta"},
            {"nivel": "INFO",    "mensaje": "Servicio iniciado"},
        ]

    def test_conteo_errores(self):
        """Debe reportar 3 eventos de nivel ERROR."""
        resultado = contar_por_nivel(self.eventos)
        self.assertEqual(resultado["ERROR"], 3)

    def test_conteo_warnings(self):
        """Debe reportar exactamente 1 evento de nivel WARNING."""
        resultado = contar_por_nivel(self.eventos)
        self.assertEqual(resultado["WARNING"], 1)


class TestDeteccionFuerzaBruta(unittest.TestCase):
    """Pruebas para la función detectar_fuerza_bruta."""

    def setUp(self):
        # Conjunto de eventos de prueba — no modificar
        self.eventos = [
            {"nivel": "ERROR",   "mensaje": "Intento de login fallido desde 10.0.0.1"},
            {"nivel": "ERROR",   "mensaje": "Intento de login fallido desde 10.0.0.1"},
            {"nivel": "ERROR",   "mensaje": "Intento de login fallido desde 10.0.0.1"},
            {"nivel": "WARNING", "mensaje": "Memoria alta"},
            {"nivel": "INFO",    "mensaje": "Servicio iniciado"},
        ]

    def test_ip_sospechosa_detectada(self):
        """10.0.0.1 con 3 fallos debe aparecer en la lista de sospechosas."""
        sospechosas = detectar_fuerza_bruta(self.eventos, umbral=3)
        self.assertIn("10.0.0.1", sospechosas)

    def test_umbral_alto_sin_alertas(self):
        """Con umbral=5 ninguna IP debe superar el límite."""
        sospechosas = detectar_fuerza_bruta(self.eventos, umbral=5)
        self.assertEqual(sospechosas, [])

    def test_eventos_info_no_generan_sospechosas(self):
        """Eventos de nivel INFO no deben producir ninguna alerta."""
        solo_info = [ev for ev in self.eventos if ev["nivel"] == "INFO"]
        sospechosas = detectar_fuerza_bruta(solo_info)
        self.assertEqual(sospechosas, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)