"""Decodificación mínima de partes SYNOP (formato OMM FM-12) para extraer precipitación.

Cada estación del SMN emite un parte SYNOP cada 3 horas. La lluvia aparece en:
  - Sección 1, grupo 6RRRt: cantidad RRR (mm) acumulada en el período t.
  - Sección 3, grupo 6RRRt: ídem, uso regional.
  - Sección 3, grupo 7RRRR: total de 24 horas en décimas de mm.
  - Indicador iR (primer dígito del grupo que sigue a la estación):
        3 = no hubo precipitación (el grupo 6 se omite porque es cero)
        4 = no se observó (dato faltante)

Este módulo convierte cada parte en "tramos": intervalos de tiempo con su lluvia.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# Código tR -> duración del período en horas (tabla OMM 4019)
PERIODO_TR = {"1": 6, "2": 12, "3": 18, "4": 24, "5": 1, "6": 2, "7": 3, "8": 9, "9": 15}

# Prioridad cuando dos tramos cubren exactamente el mismo intervalo (menor = mejor)
PRIORIDAD = {"7RRRR": 0, "6RRR-s1": 1, "6RRR-s3": 2, "iR=3": 3}


@dataclass(frozen=True)
class Tramo:
    desde: datetime
    hasta: datetime
    mm: float
    traza: bool
    origen: str  # "7RRRR", "6RRR-s1", "6RRR-s3" o "iR=3"

    @property
    def horas(self) -> int:
        return int((self.hasta - self.desde).total_seconds() // 3600)


def decodificar_rrr(rrr: str):
    """Grupo RRR (tabla OMM 3590). Devuelve (mm, es_traza) o None si falta."""
    if len(rrr) != 3 or not rrr.isdigit():
        return None
    v = int(rrr)
    if v == 990:
        return 0.0, True
    if v > 990:
        return round((v - 990) / 10, 1), False
    return float(v), False


def decodificar_r24(rrrr: str):
    """Grupo 7RRRR: total de 24 h en décimas de mm. 9999 = traza."""
    if len(rrrr) != 4 or not rrrr.isdigit():
        return None
    v = int(rrrr)
    if v == 9999:
        return 0.0, True
    return round(v / 10, 1), False


def _grupos(texto: str, estacion: str):
    """Separa el parte en (grupos sección 1, grupos sección 3). None si no aplica."""
    t = texto.replace("=", " ").split()
    try:
        i = t.index(estacion)
    except ValueError:
        return None
    resto = t[i + 1:]
    if not resto or resto[0].upper() == "NIL":
        return None
    sec1, sec3 = [], []
    actual = sec1
    for g in resto:
        if g == "333":
            actual = sec3
            continue
        if g in ("444", "555"):
            actual = None
            continue
        if actual is None:
            continue
        if len(g) == 5:
            actual.append(g)
    return sec1, sec3


def tramos_de_parte(texto: str, estacion: str, hora: datetime) -> list[Tramo]:
    """Extrae los tramos de lluvia que informa un parte emitido a `hora` (UTC)."""
    partes = _grupos(texto, estacion)
    if partes is None:
        return []
    sec1, sec3 = partes
    if len(sec1) < 2:
        return []

    tramos: list[Tramo] = []
    ir = sec1[0][0]

    # --- Sección 1 ---
    resto1 = sec1[2:]
    if resto1 and sec1[1][3:5] == "99" and resto1[0].startswith("00"):
        resto1 = resto1[1:]  # grupo 00fff de viento fuerte
    tiene_6_s1 = False
    for g in resto1:
        if g[0] == "6":
            tiene_6_s1 = True
            dec = decodificar_rrr(g[1:4])
            horas = PERIODO_TR.get(g[4])
            if dec and horas:
                tramos.append(Tramo(hora - timedelta(hours=horas), hora, dec[0], dec[1], "6RRR-s1"))
            break

    # --- Sección 3 ---
    modo_radiacion = False
    for g in sec3:
        d = g[0]
        if d in "89":
            break  # los grupos de lluvia (6 y 7) vienen antes que los 8 y 9
        if g.startswith("55"):
            modo_radiacion = True  # le siguen grupos de radiación 0..5
            continue
        if modo_radiacion and d in "012345":
            continue
        modo_radiacion = False
        if d == "6":
            dec = decodificar_rrr(g[1:4])
            horas = PERIODO_TR.get(g[4])
            if dec and horas:
                tramos.append(Tramo(hora - timedelta(hours=horas), hora, dec[0], dec[1], "6RRR-s3"))
        elif d == "7":
            dec = decodificar_r24(g[1:5])
            if dec:
                tramos.append(Tramo(hora - timedelta(hours=24), hora, dec[0], dec[1], "7RRRR"))

    # --- iR = 3: no llovió en el período del parte ---
    if ir == "3" and not tiene_6_s1:
        horas = 6 if hora.hour % 6 == 0 else 3
        tramos.append(Tramo(hora - timedelta(hours=horas), hora, 0.0, False, "iR=3"))

    return tramos


def total_ventana(tramos: list[Tramo], desde: datetime, hasta: datetime):
    """Busca la combinación de tramos contiguos que cubre exactamente [desde, hasta]
    usando la menor cantidad de tramos (los acumulados largos son más confiables).

    Devuelve (mm, traza, descripcion) o None si los partes no alcanzan para cubrir la ventana.
    """
    # Para cada intervalo exacto, quedarse con el tramo de mejor prioridad
    mejores: dict[tuple, Tramo] = {}
    for t in tramos:
        if t.desde < desde or t.hasta > hasta:
            continue
        clave = (t.desde, t.hasta)
        if clave not in mejores or PRIORIDAD[t.origen] < PRIORIDAD[mejores[clave].origen]:
            mejores[clave] = t

    por_inicio: dict[datetime, list[Tramo]] = {}
    for t in mejores.values():
        por_inicio.setdefault(t.desde, []).append(t)
    for lista in por_inicio.values():
        lista.sort(key=lambda t: (-t.horas, PRIORIDAD[t.origen]))

    # Búsqueda en anchura: el primer camino que llega a `hasta` usa la menor cantidad de tramos
    frontera = [(desde, [])]
    visitados = {desde}
    while frontera:
        siguiente = []
        for punto, camino in frontera:
            for t in por_inicio.get(punto, []):
                nuevo = camino + [t]
                if t.hasta == hasta:
                    mm = round(sum(x.mm for x in nuevo), 1)
                    traza = mm == 0 and any(x.traza for x in nuevo)
                    desc = " + ".join(f"{x.horas}h({x.origen})" for x in nuevo)
                    return mm, traza, desc
                if t.hasta not in visitados:
                    visitados.add(t.hasta)
                    siguiente.append((t.hasta, nuevo))
        frontera = siguiente
    return None
