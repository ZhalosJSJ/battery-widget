"""Carga y guarda la configuración del usuario en ~/.config/battery_widget/config.json."""

import json
import os
import sys
from pathlib import Path

CONFIG_DIR = Path(os.path.expanduser("~/.config/battery_widget"))
CONFIG_PATH = CONFIG_DIR / "config.json"

AUTOSTART_DIR = Path(os.path.expanduser("~/.config/autostart"))
AUTOSTART_PATH = AUTOSTART_DIR / "battery-widget.desktop"

# En Windows el autoarranque se hace dejando un .bat en la carpeta Startup
# del usuario (no existe el estándar XDG de Linux).
_appdata = os.environ.get("APPDATA")
AUTOSTART_PATH_WINDOWS = (
    Path(_appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "BatteryWidget.bat"
    if _appdata
    else None
)

DEFAULTS = {
    "poll_interval_seconds": 5,
    # Umbrales de aviso ordenados de mayor a menor; se notifica una sola vez
    # por cada cruce hacia abajo (con histéresis para no repetir avisos).
    "thresholds": [50, 25, 10],
    # Overrides por dispositivo: {device_id: [umbrales]}. Si un dispositivo
    # no aparece acá, usa los umbrales globales de arriba.
    "device_thresholds": {},
    "hysteresis": 5,
    "hidden_devices": [],
    "window_pos": None,
    "window_opacity": 0.92,
    "start_minimized": False,
    "notify_full_charge": True,
    "adb_enabled": True,
    # Modo mini: solo se muestra una mini batería del dispositivo elegido
    # (o el de menor porcentaje si "dispositivo_mini" es None). Por defecto
    # arranca en mini, pegado al extremo izquierdo de la pantalla (ver
    # widget.py _restaurar_posicion), con un botón propio para expandir.
    "modo_mini": True,
    "dispositivo_mini": None,
    # No molestar: pausa los avisos de umbral (no la lectura de batería).
    "no_molestar_activo": False,
    "no_molestar_hasta_ts": None,  # None + activo = indefinido hasta desactivarlo a mano
    # IDs de dispositivos ya vistos alguna vez, para avisar solo de los nuevos.
    "dispositivos_conocidos": [],
    "historial_dias_retencion": 7,
    # Panel de test de conectividad (ping bajo demanda), bajo el de batería.
    "mostrar_test_red": False,
    # Atajo de teclado global (funciona aunque la app no tenga el foco) para
    # alternar entre modo mini y tamaño completo.
    "hotkey_habilitado": True,
    "hotkey_expandir": "<ctrl>+<alt>+b",
}


def cargar():
    """Devuelve la configuración actual, combinando con los valores por defecto."""
    config = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                guardado = json.load(f)
            if isinstance(guardado, dict):
                config.update(guardado)
        except (json.JSONDecodeError, OSError):
            pass
    return config


def guardar(config):
    """Persiste la configuración en disco, creando el directorio si falta."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def autostart_activo():
    if sys.platform.startswith("linux"):
        return AUTOSTART_PATH.exists()
    if AUTOSTART_PATH_WINDOWS is not None:
        return AUTOSTART_PATH_WINDOWS.exists()
    return False


def set_autostart(activo, comando):
    """Crea o elimina el lanzador de autoarranque (.desktop en Linux, .bat en Windows)."""
    if sys.platform.startswith("linux"):
        if activo:
            AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            contenido = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Battery Widget\n"
                f"Exec={comando}\n"
                "X-GNOME-Autostart-enabled=true\n"
                "NoDisplay=false\n"
                "Comment=Widget de niveles de batería de dispositivos conectados\n"
            )
            with open(AUTOSTART_PATH, "w", encoding="utf-8") as f:
                f.write(contenido)
        elif AUTOSTART_PATH.exists():
            AUTOSTART_PATH.unlink()
        return

    if AUTOSTART_PATH_WINDOWS is None:
        return  # no se encontró %APPDATA%; no hay dónde dejar el autoarranque
    if activo:
        AUTOSTART_PATH_WINDOWS.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTOSTART_PATH_WINDOWS, "w", encoding="utf-8") as f:
            f.write(f'@echo off\r\nstart "" {comando}\r\n')
    elif AUTOSTART_PATH_WINDOWS.exists():
        AUTOSTART_PATH_WINDOWS.unlink()
