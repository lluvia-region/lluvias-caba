"""Descarga de partes SYNOP emitidos por el SMN.

El SMN no publica la lluvia diaria en un archivo abierto. Sus estaciones sí envían
cada 3 horas partes SYNOP a la red mundial de la OMM, y Ogimet (ogimet.com) los
archiva y los deja consultar. Los datos son las observaciones originales del SMN;
Ogimet solo los retransmite.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

URL = "https://www.ogimet.com/cgi-bin/getsynop"
USER_AGENT = "lluvias-caba/1.0 (recolector diario, 2 consultas por dia; github actions)"

# Formato de cada línea: IIiii,AAAA,MM,DD,HH,mm,AAXX ... =
LINEA = re.compile(r"^(\d{5}),(\d{4}),(\d{2}),(\d{2}),(\d{2}),(\d{2}),(.*)$")


class ErrorDescarga(Exception):
    pass


def parsear(cuerpo: str):
    """Convierte la respuesta de Ogimet en una lista de (estacion, hora_utc, texto)."""
    partes = []
    for linea in cuerpo.splitlines():
        m = LINEA.match(linea.strip())
        if not m:
            continue
        est, a, me, d, h, mi, texto = m.groups()
        hora = datetime(int(a), int(me), int(d), int(h), int(mi), tzinfo=timezone.utc)
        partes.append((est, hora, texto.strip()))
    return partes


def descargar(estacion: str, desde: datetime, hasta: datetime, intentos: int = 3) -> list:
    params = urllib.parse.urlencode({
        "block": estacion,
        "begin": desde.strftime("%Y%m%d%H%M"),
        "end": hasta.strftime("%Y%m%d%H%M"),
    })
    url = f"{URL}?{params}"
    ultimo_error = None
    for n in range(1, intentos + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=90) as r:
                cuerpo = r.read().decode("latin-1")
            partes = parsear(cuerpo)
            if not partes and cuerpo.strip():
                # Ogimet responde texto (no partes) cuando hay un error o se superó la cuota
                muestra = " ".join(cuerpo.split())[:200]
                raise ErrorDescarga(f"Respuesta sin partes SYNOP: {muestra!r}")
            return partes
        except (urllib.error.URLError, TimeoutError, ErrorDescarga) as e:
            ultimo_error = e
            if n < intentos:
                time.sleep(20 * n)
    raise ErrorDescarga(f"No se pudo descargar {estacion}: {ultimo_error}")
