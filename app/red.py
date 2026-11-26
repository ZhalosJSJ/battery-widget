"""Prueba de conectividad/latencia bajo demanda (no corre en segundo plano,
solo se ejecuta cuando el usuario aprieta el botón)."""

import os
import platform
import re
import subprocess
import time
import urllib.error
import urllib.request

HOSTS_PRUEBA = ["1.1.1.1", "8.8.8.8"]
CANTIDAD_PINGS = 4
TIMEOUT_SEGUNDOS = 2

# Endpoints públicos de Cloudflare para medir velocidad (los mismos que usa
# speed.cloudflare.com). No hace falta cuenta ni API key.
URL_DESCARGA = "https://speed.cloudflare.com/__down?bytes={}"
URL_SUBIDA = "https://speed.cloudflare.com/__up"
BYTES_DESCARGA = 4_000_000
BYTES_SUBIDA = 1_500_000
TIMEOUT_TRANSFERENCIA = 10

# Cloudflare bloquea el User-Agent por defecto de urllib (lo trata como bot);
# con uno de navegador normal responde sin problema.
_HEADERS = {"User-Agent": "Mozilla/5.0 (BatteryWidget speed test)"}


def _comando_ping(host):
    if platform.system() == "Windows":
        return ["ping", "-n", str(CANTIDAD_PINGS), "-w", str(TIMEOUT_SEGUNDOS * 1000), host]
    return ["ping", "-c", str(CANTIDAD_PINGS), "-W", str(TIMEOUT_SEGUNDOS), host]


def _medir_host(host):
    try:
        resultado = subprocess.run(
            _comando_ping(host),
            capture_output=True,
            text=True,
            timeout=CANTIDAD_PINGS * TIMEOUT_SEGUNDOS + 5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"host": host, "latencia_ms": None, "perdida_pct": 100.0, "ok": False}

    salida = resultado.stdout

    perdida_pct = 100.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:packet\s*)?loss", salida, re.IGNORECASE)
    if m:
        perdida_pct = float(m.group(1))

    latencia_ms = None
    # Linux/macOS: "rtt min/avg/max/mdev = 12.1/14.5/18.2/2.1 ms"
    m = re.search(r"=\s*[\d.]+/([\d.]+)/[\d.]+(?:/[\d.]+)?\s*ms", salida)
    if m:
        latencia_ms = float(m.group(1))
    else:
        # Windows: "Average = 23ms"
        m = re.search(r"Average\s*=\s*(\d+)\s*ms", salida, re.IGNORECASE)
        if m:
            latencia_ms = float(m.group(1))

    return {
        "host": host,
        "latencia_ms": latencia_ms,
        "perdida_pct": perdida_pct,
        "ok": latencia_ms is not None and perdida_pct < 100,
    }


def ejecutar_test(hosts=None):
    """Prueba uno o más hosts (secuencial) y devuelve el mejor resultado utilizable."""
    hosts = hosts or HOSTS_PRUEBA
    resultados = [_medir_host(h) for h in hosts]
    utilizables = [r for r in resultados if r["ok"]]
    mejor = min(utilizables, key=lambda r: r["latencia_ms"]) if utilizables else resultados[0]
    return {"mejor": mejor, "resultados": resultados}


def medir_descarga():
    """Mbps de bajada, cronometrando la descarga de un archivo de prueba.
    Es una medición aproximada de una sola conexión (no un test de laboratorio
    con múltiples streams en paralelo), pero sirve como referencia rápida."""
    try:
        peticion = urllib.request.Request(URL_DESCARGA.format(BYTES_DESCARGA), headers=_HEADERS)
        inicio = time.monotonic()
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_TRANSFERENCIA) as resp:
            datos = resp.read()
        elapsed = time.monotonic() - inicio
        if elapsed <= 0 or not datos:
            return None
        return (len(datos) * 8 / elapsed) / 1_000_000
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return None


def medir_subida():
    """Mbps de subida, cronometrando el envío de un bloque de datos de prueba."""
    try:
        payload = os.urandom(BYTES_SUBIDA)
        peticion = urllib.request.Request(URL_SUBIDA, data=payload, method="POST", headers=_HEADERS)
        inicio = time.monotonic()
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_TRANSFERENCIA) as resp:
            resp.read()
        elapsed = time.monotonic() - inicio
        if elapsed <= 0:
            return None
        return (len(payload) * 8 / elapsed) / 1_000_000
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return None


def clasificar(latencia_ms, perdida_pct):
    """(nivel 0-4, color, etiqueta), al estilo de un indicador de señal de videojuego."""
    if latencia_ms is None or perdida_pct >= 100:
        return 0, "#ef4444", "Sin conexión"
    if perdida_pct > 5 or latencia_ms > 150:
        return 1, "#ef4444", "Mala"
    if latencia_ms > 80:
        return 2, "#eab308", "Regular"
    if latencia_ms > 30:
        return 3, "#84cc16", "Buena"
    return 4, "#22c55e", "Excelente"
