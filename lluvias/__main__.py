"""Uso:
    python -m lluvias diario                 # descarga y recalcula los últimos días (lo corre GitHub Actions)
    python -m lluvias historico --desde 2025-01-01 [--hasta 2025-12-31]
    python -m lluvias recalcular             # recalcula todo desde los partes guardados
    python -m lluvias diagnostico            # muestra partes crudos y cómo se interpretan
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import db, fuente
from .synop import tramos_de_parte, total_ventana

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
ESTACIONES = CONFIG["estaciones"]
RUTA_DB = RAIZ / "data" / "lluvias.db"
RUTA_CSV = RAIZ / "data" / "lluvias.csv"
RUTA_JSON = RAIZ / "docs" / "datos.json"


def ventana(fecha: date):
    """Día pluviométrico: de las 9:00 de `fecha` a las 9:00 del día siguiente (hora argentina = 12 UTC)."""
    desde = datetime(fecha.year, fecha.month, fecha.day, 12, tzinfo=timezone.utc)
    return desde, desde + timedelta(days=1)


def ultima_fecha_cerrada(ahora: datetime) -> date:
    fin = ahora.date() if ahora.hour >= 12 else ahora.date() - timedelta(days=1)
    return fin - timedelta(days=1)


def calcular_dia(con, estacion: str, fecha: date):
    desde, hasta = ventana(fecha)
    tramos = []
    for hora, texto in db.partes_entre(con, estacion, desde + timedelta(minutes=1), hasta):
        tramos.extend(tramos_de_parte(texto, estacion, hora))
    res = total_ventana(tramos, desde, hasta)
    if res:
        mm, traza, metodo = res
        db.guardar_dia(con, estacion, fecha.isoformat(), mm, traza, True, metodo, desde, hasta)
        return mm, traza, True
    db.guardar_dia(con, estacion, fecha.isoformat(), None, False, False,
                   f"incompleto: {len(tramos)} tramos con datos", desde, hasta)
    return None, False, False


def fechas(desde: date, hasta: date):
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


def exportar(con):
    n = db.exportar_csv(con, RUTA_CSV)
    db.exportar_json(con, RUTA_JSON, ESTACIONES)
    print(f"Exportados {n} registros a {RUTA_CSV.relative_to(RAIZ)} y {RUTA_JSON.relative_to(RAIZ)}")


def resumen(con, n=7):
    lineas = ["## Lluvia diaria (día pluviométrico de 9 a 9 h)", "",
              "| Fecha | " + " | ".join(e["corto"] for e in ESTACIONES) + " |",
              "|---|" + "---|" * len(ESTACIONES)]
    por_est = {e["id"]: {f: (mm, tr, c) for f, mm, tr, c, _ in db.ultimos_dias(con, e["id"], n)}
               for e in ESTACIONES}
    todas = sorted({f for d in por_est.values() for f in d}, reverse=True)[:n]
    for f in todas:
        celdas = []
        for e in ESTACIONES:
            v = por_est[e["id"]].get(f)
            if not v or not v[2]:
                celdas.append("sin datos completos")
            elif v[1]:
                celdas.append("traza")
            else:
                celdas.append(f"{v[0]:.1f} mm")
        lineas.append(f"| {f} | " + " | ".join(celdas) + " |")
    texto = "\n".join(lineas)
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto + "\n")


def cmd_diario(args):
    con = db.conectar(RUTA_DB)
    db.guardar_estaciones(con, ESTACIONES)
    ahora = datetime.now(timezone.utc)
    f_fin = ultima_fecha_cerrada(ahora)
    f_ini = f_fin - timedelta(days=args.dias - 1)
    desde, _ = ventana(f_ini)
    _, hasta = ventana(f_fin)

    errores = 0
    for i, e in enumerate(ESTACIONES):
        if i:
            time.sleep(CONFIG["pausa_entre_descargas_seg"])
        try:
            partes = fuente.descargar(e["id"], desde, hasta + timedelta(hours=1))
            n = db.guardar_partes(con, partes)
            print(f"{e['corto']}: {len(partes)} partes recibidos ({n} nuevos o actualizados)")
        except fuente.ErrorDescarga as err:
            errores += 1
            print(f"::error::{e['corto']}: {err}")

    for e in ESTACIONES:
        for f in fechas(f_ini, f_fin):
            calcular_dia(con, e["id"], f)
    exportar(con)
    resumen(con)

    # Señal de alarma: ninguna estación tiene datos completos en los últimos 3 días
    sin_datos = all(
        not any(c for _, _, _, c, _ in db.ultimos_dias(con, e["id"], 3)) for e in ESTACIONES
    )
    if errores == len(ESTACIONES) or sin_datos:
        print("::error::No se obtuvieron datos válidos. Revisá el registro de esta ejecución.")
        return 1
    return 0


def cmd_historico(args):
    con = db.conectar(RUTA_DB)
    db.guardar_estaciones(con, ESTACIONES)
    f_ini = date.fromisoformat(args.desde)
    f_fin = date.fromisoformat(args.hasta) if args.hasta else ultima_fecha_cerrada(datetime.now(timezone.utc))
    bloque = timedelta(days=args.bloque)
    fallos = 0
    for e in ESTACIONES:
        d = f_ini
        while d <= f_fin:
            d_fin = min(d + bloque - timedelta(days=1), f_fin)
            desde, _ = ventana(d)
            _, hasta = ventana(d_fin)
            try:
                partes = fuente.descargar(e["id"], desde, hasta + timedelta(hours=1))
                db.guardar_partes(con, partes)
                print(f"{e['corto']} {d} a {d_fin}: {len(partes)} partes")
            except fuente.ErrorDescarga as err:
                fallos += 1
                print(f"::warning::{e['corto']} {d} a {d_fin}: {err}")
            time.sleep(CONFIG["pausa_entre_descargas_seg"])
            d = d_fin + timedelta(days=1)
        for f in fechas(f_ini, f_fin):
            calcular_dia(con, e["id"], f)
    exportar(con)
    resumen(con, 10)
    print(f"Bloques con error: {fallos}. Podés volver a correr el mismo rango: lo ya guardado no se duplica.")
    return 0


def cmd_recalcular(args):
    con = db.conectar(RUTA_DB)
    db.guardar_estaciones(con, ESTACIONES)
    for e in ESTACIONES:
        r = con.execute("SELECT MIN(hora_utc), MAX(hora_utc) FROM partes_synop WHERE estacion=?",
                        (e["id"],)).fetchone()
        if not r[0]:
            continue
        f_ini = date.fromisoformat(r[0][:10]) - timedelta(days=1)
        f_fin = date.fromisoformat(r[1][:10])
        for f in fechas(f_ini, f_fin):
            calcular_dia(con, e["id"], f)
    exportar(con)
    resumen(con)
    return 0


def cmd_diagnostico(args):
    ahora = datetime.now(timezone.utc)
    f = ultima_fecha_cerrada(ahora)
    desde, hasta = ventana(f)
    for e in ESTACIONES:
        print(f"\n=== {e['nombre']} ({e['id']}) — día pluviométrico {f} ===")
        try:
            partes = fuente.descargar(e["id"], desde, hasta + timedelta(hours=1))
        except fuente.ErrorDescarga as err:
            print(f"ERROR: {err}")
            continue
        tramos = []
        for _, hora, texto in partes:
            t = tramos_de_parte(texto, e["id"], hora)
            tramos.extend(t)
            print(f"{hora:%Y-%m-%d %H:%MZ}  {texto}")
            for x in t:
                print(f"      -> {x.horas}h {x.origen}: {'traza' if x.traza else f'{x.mm} mm'}")
        print("Total:", total_ventana(tramos, desde, hasta) or "no alcanza para cubrir las 24 h")
        time.sleep(CONFIG["pausa_entre_descargas_seg"])
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="lluvias")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("diario")
    s.add_argument("--dias", type=int, default=CONFIG["dias_a_reprocesar"])
    s = sub.add_parser("historico")
    s.add_argument("--desde", required=True, help="AAAA-MM-DD")
    s.add_argument("--hasta", help="AAAA-MM-DD (por defecto, ayer)")
    s.add_argument("--bloque", type=int, default=10, help="días por consulta")
    sub.add_parser("recalcular")
    sub.add_parser("diagnostico")
    args = p.parse_args(argv)
    return {"diario": cmd_diario, "historico": cmd_historico,
            "recalcular": cmd_recalcular, "diagnostico": cmd_diagnostico}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
