import unittest
from datetime import datetime, timedelta, timezone

from lluvias.synop import decodificar_rrr, tramos_de_parte, total_ventana

UTC = timezone.utc
D0 = datetime(2026, 10, 8, 12, tzinfo=UTC)   # 9 h del 8/10
D1 = D0 + timedelta(days=1)                  # 9 h del 9/10


def h(dt_offset_horas):
    return D0 + timedelta(hours=dt_offset_horas)


class Decodificacion(unittest.TestCase):
    def test_rrr(self):
        self.assertEqual(decodificar_rrr("012"), (12.0, False))
        self.assertEqual(decodificar_rrr("990"), (0.0, True))
        self.assertEqual(decodificar_rrr("994"), (0.4, False))
        self.assertIsNone(decodificar_rrr("///"))

    def test_24h_prefiere_7rrrr(self):
        p = "AAXX 09124 87585 12970 51804 10152 20098 39985 40112 52010 60124 70222 333 10201 20089 70253 81/// ="
        t = tramos_de_parte(p, "87585", D1)
        self.assertEqual({x.origen for x in t}, {"6RRR-s1", "7RRRR"})
        self.assertEqual(total_ventana(t, D0, D1)[0], 25.3)

    def test_nil(self):
        self.assertEqual(tramos_de_parte("AAXX 09124 87585 NIL=", "87585", D1), [])

    def test_viento_fuerte_00fff(self):
        p = "AAXX 09124 87582 12970 81899 00102 10152 20098 60052 81///="
        t = tramos_de_parte(p, "87582", D1)
        self.assertEqual(len(t), 1)
        self.assertEqual((t[0].mm, t[0].horas), (5.0, 12))

    def test_grupo_55_radiacion_no_se_confunde(self):
        p = "AAXX 09124 87585 32970 51804 10152 333 55080 20123 30045 60071 81///="
        t = tramos_de_parte(p, "87585", D1)
        origenes = {x.origen: x for x in t}
        self.assertIn("6RRR-s3", origenes)
        self.assertEqual(origenes["6RRR-s3"].mm, 7.0)
        self.assertEqual(origenes["6RRR-s3"].horas, 6)


class TotalDiario(unittest.TestCase):
    def test_suma_cuatro_periodos_de_6h(self):
        partes = [
            (h(6), "AAXX 08184 87585 12970 51804 10152 60031 ="),
            (h(12), "AAXX 09004 87585 12970 51804 10152 60101 ="),
            (h(18), "AAXX 09064 87585 32970 51804 10152 ="),
            (h(24), "AAXX 09124 87585 12970 51804 10152 69931 ="),
        ]
        t = [x for hora, p in partes for x in tramos_de_parte(p, "87585", hora)]
        mm, traza, metodo = total_ventana(t, D0, D1)
        self.assertEqual(mm, 13.3)
        self.assertEqual(metodo.count("+"), 3)

    def test_dos_periodos_de_12h(self):
        partes = [
            (h(12), "AAXX 09004 87582 12970 51804 10152 60082 ="),
            (h(24), "AAXX 09124 87582 12970 51804 10152 60152 ="),
        ]
        t = [x for hora, p in partes for x in tramos_de_parte(p, "87582", hora)]
        self.assertEqual(total_ventana(t, D0, D1)[0], 23.0)

    def test_sin_lluvia_por_ir3(self):
        partes = [(h(k), f"AAXX 0{(8 + (12 + k) // 24)}{(12 + k) % 24:02d}4 87585 32970 51804 10152 =")
                  for k in (6, 12, 18, 24)]
        t = [x for hora, p in partes for x in tramos_de_parte(p, "87585", hora)]
        mm, traza, _ = total_ventana(t, D0, D1)
        self.assertEqual((mm, traza), (0.0, False))

    def test_traza(self):
        t = tramos_de_parte("AAXX 09124 87585 12970 51804 10152 69904 =", "87585", D1)
        self.assertEqual(total_ventana(t, D0, D1)[:2], (0.0, True))

    def test_incompleto_si_falta_un_parte(self):
        partes = [
            (h(6), "AAXX 08184 87585 12970 51804 10152 60031 ="),
            (h(12), "AAXX 09004 87585 12970 51804 10152 60101 ="),
            (h(24), "AAXX 09124 87585 12970 51804 10152 60011 ="),
        ]
        t = [x for hora, p in partes for x in tramos_de_parte(p, "87585", hora)]
        self.assertIsNone(total_ventana(t, D0, D1))


if __name__ == "__main__":
    unittest.main()
