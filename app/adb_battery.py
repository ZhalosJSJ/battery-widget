"""Lectura de batería de un celular Android conectado por USB, vía ADB.

Requiere el binario `adb` instalado (paquete `android-tools-adb` en
Debian/Ubuntu/Mint) y que el celular tenga la depuración USB activada y
autorizado este computador (se pide una vez, con un diálogo en el propio
celular).
"""

import re
import shutil
import subprocess

TIMEOUT_SEGUNDOS = 3

# BatteryManager.STATUS de Android: 2=cargando, 5=carga completa.
_ESTADOS_CARGANDO = {2, 5}


def adb_disponible():
    return shutil.which("adb") is not None


def listar_dispositivos_android():
    """Devuelve una lista de dicts (mismo formato que app.upower) por cada
    celular Android conectado por USB, autorizado y con `adb` respondiendo.
    Si `adb` no está instalado o no hay celulares autorizados, devuelve []."""
    if not adb_disponible():
        return []

    try:
        resultado = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEGUNDOS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    dispositivos = []
    for linea in resultado.stdout.splitlines()[1:]:
        linea = linea.strip()
        if not linea or "\t" not in linea:
            continue
        serial, estado = linea.split("\t", 1)
        estado = estado.strip()
        if estado != "device":
            # "unauthorized" (falta aceptar el diálogo en el celular),
            # "offline", etc.: se muestra igual como aviso, para que el
            # usuario sepa que hay que hacer algo en el propio celular.
            dispositivos.append(_dispositivo_pendiente(serial, estado))
            continue
        info = _leer_bateria(serial)
        if info is not None:
            dispositivos.append(info)
    return dispositivos


_MENSAJES_PENDIENTE = {
    "unauthorized": "autoriza la depuración USB en el celular",
    "offline": "reconectando…",
}


def _dispositivo_pendiente(serial, estado):
    return {
        "path": f"adb:{serial}",
        "id": f"adb_{serial}",
        "nombre": f"Android ({serial})",
        "vendor": "",
        "type": 8,  # Teléfono
        "type_name": "Teléfono",
        "state": 0,
        "state_name": _MENSAJES_PENDIENTE.get(estado, estado),
        "is_charging": False,
        "porcentaje": None,
        "icon_name": "",
        "is_present": True,
        "tiempo_restante_seg": 0,
        "tiempo_carga_seg": 0,
    }


def _leer_bateria(serial):
    try:
        resultado = subprocess.run(
            ["adb", "-s", serial, "shell", "dumpsys", "battery"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEGUNDOS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    salida = resultado.stdout
    nivel = _extraer_entero(salida, "level")
    if nivel is None:
        return None
    estado = _extraer_entero(salida, "status") or 0

    nombre = _nombre_modelo(serial) or f"Android ({serial})"

    return {
        "path": f"adb:{serial}",
        "id": f"adb_{serial}",
        "nombre": nombre,
        "vendor": "",
        "type": 8,  # Teléfono
        "type_name": "Teléfono",
        "state": estado,
        "state_name": "Cargando" if estado in _ESTADOS_CARGANDO else "Descargando",
        "is_charging": estado in _ESTADOS_CARGANDO,
        "porcentaje": float(nivel),
        "icon_name": "",
        "is_present": True,
        # Android/dumpsys no entrega una estimación de tiempo restante.
        "tiempo_restante_seg": 0,
        "tiempo_carga_seg": 0,
    }


def _nombre_modelo(serial):
    try:
        resultado = subprocess.run(
            ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEGUNDOS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    nombre = resultado.stdout.strip()
    return nombre or None


def _extraer_entero(texto, campo):
    coincidencia = re.search(rf"{campo}:\s*(-?\d+)", texto)
    return int(coincidencia.group(1)) if coincidencia else None
