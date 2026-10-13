import unittest
from copy import deepcopy

from solution import calcular_totales_por_asignatura


class TestCalcularTotalesPorAsignatura(unittest.TestCase):
    def test_lista_vacia(self):
        self.assertEqual(calcular_totales_por_asignatura([]), {})

    def test_dos_asignaturas_distintas(self):
        sesiones = [
            {"asignatura": "Python", "minutos": 20},
            {"asignatura": "Redes", "minutos": 30},
        ]

        self.assertEqual(
            calcular_totales_por_asignatura(sesiones),
            {"Python": 20, "Redes": 30},
        )

    def test_acumulacion_asignatura_repetida(self):
        sesiones = [
            {"asignatura": "Python", "minutos": 20},
            {"asignatura": "Redes", "minutos": 30},
            {"asignatura": "Python", "minutos": 15},
        ]

        self.assertEqual(
            calcular_totales_por_asignatura(sesiones),
            {"Python": 35, "Redes": 30},
        )

    def test_entrada_permanece_intacta(self):
        sesiones = [
            {"asignatura": "Python", "minutos": 20},
            {"asignatura": "Redes", "minutos": 30},
            {"asignatura": "Python", "minutos": 15},
        ]
        original = deepcopy(sesiones)

        calcular_totales_por_asignatura(sesiones)

        self.assertEqual(sesiones, original)


if __name__ == "__main__":
    unittest.main()
