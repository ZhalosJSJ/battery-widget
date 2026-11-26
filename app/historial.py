"""Historial de lecturas de batería, guardado en SQLite para graficarlo después."""

import os
import sqlite3
import time
from pathlib import Path

HISTORIAL_DIR = Path(os.path.expanduser("~/.config/battery_widget"))
HISTORIAL_PATH = HISTORIAL_DIR / "historial.db"

# No tiene sentido guardar una fila por cada poll de 5s: se agrupa por
# dispositivo y solo se guarda una lectura cada este tanto tiempo.
INTERVALO_MINIMO_SEGUNDOS = 60


class Historial:
    def __init__(self, ruta=None):
        self.ruta = ruta or HISTORIAL_PATH
        HISTORIAL_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.ruta))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lecturas (
                ts INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                device_name TEXT NOT NULL,
                porcentaje REAL NOT NULL,
                is_charging INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lecturas_device_ts ON lecturas(device_id, ts)"
        )
        self._conn.commit()
        self._ultimo_registro = {}  # device_id -> timestamp del último insert

    def registrar(self, dispositivos, ahora=None):
        """Guarda una lectura por dispositivo, como máximo una cada
        INTERVALO_MINIMO_SEGUNDOS por dispositivo."""
        ahora = ahora if ahora is not None else time.time()
        filas = []
        for d in dispositivos:
            if d["porcentaje"] is None:
                continue
            ultimo = self._ultimo_registro.get(d["id"])
            if ultimo is not None and (ahora - ultimo) < INTERVALO_MINIMO_SEGUNDOS:
                continue
            self._ultimo_registro[d["id"]] = ahora
            filas.append((int(ahora), d["id"], d["nombre"], float(d["porcentaje"]), int(bool(d["is_charging"]))))

        if filas:
            self._conn.executemany(
                "INSERT INTO lecturas (ts, device_id, device_name, porcentaje, is_charging) VALUES (?, ?, ?, ?, ?)",
                filas,
            )
            self._conn.commit()

    def dispositivos_con_historial(self):
        """Devuelve [(device_id, device_name)] de los dispositivos con al menos una lectura,
        usando el nombre más reciente registrado para cada uno."""
        cur = self._conn.execute(
            """
            SELECT device_id, device_name FROM lecturas
            WHERE ts IN (SELECT MAX(ts) FROM lecturas GROUP BY device_id)
            ORDER BY device_name COLLATE NOCASE
            """
        )
        return cur.fetchall()

    def leer(self, device_id, desde_ts):
        cur = self._conn.execute(
            "SELECT ts, porcentaje, is_charging FROM lecturas WHERE device_id = ? AND ts >= ? ORDER BY ts",
            (device_id, int(desde_ts)),
        )
        return cur.fetchall()

    def purgar_antiguos(self, dias_retencion):
        limite = time.time() - dias_retencion * 86400
        self._conn.execute("DELETE FROM lecturas WHERE ts < ?", (int(limite),))
        self._conn.commit()

    def cerrar(self):
        self._conn.close()
