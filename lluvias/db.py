"""Base de datos SQLite: partes crudos (para auditar y recalcular) y lluvia diaria."""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS estaciones (
    id      TEXT PRIMARY KEY,   -- indicativo OMM (p. ej. 87585)
    nombre  TEXT NOT NULL,
    lat     REAL,
    lon     REAL
);

CREATE TABLE IF NOT EXISTS partes_synop (
    estacion  TEXT NOT NULL,
    hora_utc  TEXT NOT NULL,     -- AAAA-MM-DDTHH:MMZ
    texto     TEXT NOT NULL,     -- parte SYNOP tal como se recibió
    PRIMARY KEY (estacion, hora_utc)
);

CREATE TABLE IF NOT EXISTS lluvia_diaria (
    estacion        TEXT NOT NULL,
    fecha           TEXT NOT NULL,  -- día pluviométrico: de las 9 h de esta fecha a las 9 h del día siguiente
    mm              REAL,           -- NULL si los partes recibidos no alcanzan para calcularlo
    traza           INTEGER NOT NULL DEFAULT 0,  -- 1 = llovió menos de 0,1 mm
    completo        INTEGER NOT NULL,            -- 1 = el período de 24 h está cubierto
    metodo          TEXT,           -- qué grupos SYNOP se usaron
    desde_utc       TEXT NOT NULL,
    hasta_utc       TEXT NOT NULL,
    actualizado_utc TEXT NOT NULL,
    PRIMARY KEY (estacion, fecha)
);
"""


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _desde_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def conectar(ruta: Path) -> sqlite3.Connection:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.executescript(ESQUEMA)
    return con


def guardar_estaciones(con, estaciones):
    con.executemany(
        "INSERT INTO estaciones (id, nombre, lat, lon) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre, lat=excluded.lat, lon=excluded.lon",
        [(e["id"], e["nombre"], e.get("lat"), e.get("lon")) for e in estaciones],
    )
    con.commit()


def guardar_partes(con, partes) -> int:
    antes = con.total_changes
    con.executemany(
        "INSERT INTO partes_synop (estacion, hora_utc, texto) VALUES (?, ?, ?) "
        "ON CONFLICT(estacion, hora_utc) DO UPDATE SET texto=excluded.texto",
        [(est, _iso(hora), texto) for est, hora, texto in partes],
    )
    con.commit()
    return con.total_changes - antes


def partes_entre(con, estacion: str, desde: datetime, hasta: datetime):
    filas = con.execute(
        "SELECT hora_utc, texto FROM partes_synop WHERE estacion=? AND hora_utc BETWEEN ? AND ? "
        "ORDER BY hora_utc",
        (estacion, _iso(desde), _iso(hasta)),
    ).fetchall()
    return [(_desde_iso(h), t) for h, t in filas]


def guardar_dia(con, estacion, fecha, mm, traza, completo, metodo, desde, hasta):
    """Guarda o actualiza un día. Nunca pisa un valor completo con uno incompleto."""
    actual = con.execute(
        "SELECT completo FROM lluvia_diaria WHERE estacion=? AND fecha=?", (estacion, fecha)
    ).fetchone()
    if actual and actual[0] == 1 and not completo:
        return
    con.execute(
        "INSERT INTO lluvia_diaria (estacion, fecha, mm, traza, completo, metodo, desde_utc, hasta_utc, actualizado_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(estacion, fecha) DO UPDATE SET mm=excluded.mm, traza=excluded.traza, "
        "completo=excluded.completo, metodo=excluded.metodo, desde_utc=excluded.desde_utc, "
        "hasta_utc=excluded.hasta_utc, actualizado_utc=excluded.actualizado_utc",
        (estacion, fecha, mm, int(traza), int(completo), metodo, _iso(desde), _iso(hasta),
         _iso(datetime.now(timezone.utc))),
    )
    con.commit()


def ultimos_dias(con, estacion: str, n: int):
    return con.execute(
        "SELECT fecha, mm, traza, completo, metodo FROM lluvia_diaria WHERE estacion=? "
        "ORDER BY fecha DESC LIMIT ?", (estacion, n)
    ).fetchall()


def exportar_csv(con, ruta: Path):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    filas = con.execute(
        "SELECT d.fecha, d.estacion, e.nombre, d.mm, d.traza, d.completo, d.metodo, d.desde_utc, d.hasta_utc "
        "FROM lluvia_diaria d JOIN estaciones e ON e.id = d.estacion ORDER BY d.fecha, d.estacion"
    ).fetchall()
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "estacion_id", "estacion", "lluvia_mm", "traza", "completo", "metodo",
                    "desde_utc", "hasta_utc"])
        for fecha, est, nombre, mm, traza, completo, metodo, d, h in filas:
            w.writerow([fecha, est, nombre, "" if mm is None else f"{mm:.1f}", traza, completo,
                        metodo or "", d, h])
    return len(filas)


def exportar_json(con, ruta: Path, estaciones):
    """Datos compactos para la página web (docs/)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    filas = con.execute(
        "SELECT estacion, fecha, mm, traza, completo FROM lluvia_diaria ORDER BY fecha"
    ).fetchall()
    datos = {
        "generado_utc": _iso(datetime.now(timezone.utc)),
        "estaciones": [{"id": e["id"], "nombre": e["nombre"], "corto": e.get("corto", e["nombre"])}
                       for e in estaciones],
        "dias": [[est, fecha, mm, traza, completo] for est, fecha, mm, traza, completo in filas],
    }
    ruta.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
