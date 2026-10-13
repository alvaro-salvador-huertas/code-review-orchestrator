import unittest

from solution import clasificar_ejecucion


class TestClasificarEjecucion(unittest.TestCase):
    def test_codigo_cero_y_texto_valido(self):
        self.assertEqual(
            clasificar_ejecucion(0, "Trabajo terminado"),
            "completada",
        )

    def test_codigo_cero_y_cadena_vacia(self):
        self.assertEqual(
            clasificar_ejecucion(0, ""),
            "respuesta_vacia",
        )

    def test_codigo_cero_y_espacios_y_saltos_de_linea(self):
        self.assertEqual(
            clasificar_ejecucion(0, "  \n \n  "),
            "respuesta_vacia",
        )

    def test_codigo_cero_y_respuesta_none(self):
        self.assertEqual(
            clasificar_ejecucion(0, None),
            "respuesta_vacia",
        )

    def test_codigo_distinto_de_cero_y_texto_presente(self):
        self.assertEqual(
            clasificar_ejecucion(1, "Texto producido antes del fallo"),
            "fallo_ejecucion",
        )

    def test_codigo_distinto_de_cero_y_respuesta_vacia(self):
        self.assertEqual(
            clasificar_ejecucion(1, ""),
            "fallo_ejecucion",
        )

    def test_codigo_none_sin_tiempo_agotado(self):
        self.assertEqual(
            clasificar_ejecucion(None, None, tiempo_agotado=False),
            "fallo_ejecucion",
        )

    def test_tiempo_agotado_prevalece_con_codigo_cero_y_texto(self):
        self.assertEqual(
            clasificar_ejecucion(0, "Trabajo terminado", tiempo_agotado=True),
            "tiempo_agotado",
        )


if __name__ == "__main__":
    unittest.main()
