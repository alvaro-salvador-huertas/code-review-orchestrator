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

    def test_codigo_cero_y_tabuladores(self):
        self.assertEqual(clasificar_ejecucion(0, "\t\t"), "respuesta_vacia")

    def test_codigo_cero_y_retorno_de_carro(self):
        self.assertEqual(clasificar_ejecucion(0, "\r\r"), "respuesta_vacia")

    def test_codigo_cero_y_combinacion_de_espacios_en_blanco(self):
        self.assertEqual(clasificar_ejecucion(0, " \t\n\r\v\f "), "respuesta_vacia")

    def test_codigo_cero_y_espacio_no_separable_unicode(self):
        self.assertEqual(clasificar_ejecucion(0, "\u00a0"), "respuesta_vacia")

    def test_codigo_cero_y_texto_rodeado_de_espacios_en_blanco(self):
        self.assertEqual(
            clasificar_ejecucion(0, " \t\r\n\u00a0Trabajo terminado\u00a0\v\f "),
            "completada",
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

    def test_codigo_distinto_de_cero_prevalece_sobre_espacios_en_blanco(self):
        self.assertEqual(clasificar_ejecucion(-1, " \t\r\n\u00a0"), "fallo_ejecucion")

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

    def test_tiempo_agotado_prevalece_con_codigo_cero_y_espacios_en_blanco(self):
        self.assertEqual(
            clasificar_ejecucion(0, "\t\r\u00a0", tiempo_agotado=True),
            "tiempo_agotado",
        )

    def test_tiempo_agotado_prevalece_sobre_fallo_y_espacios_en_blanco(self):
        self.assertEqual(
            clasificar_ejecucion(1, "\t\r\u00a0", tiempo_agotado=True),
            "tiempo_agotado",
        )


if __name__ == "__main__":
    unittest.main()
