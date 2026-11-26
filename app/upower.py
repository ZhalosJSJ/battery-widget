"""Cliente para leer niveles de batería de dispositivos vía UPower (D-Bus)."""

import dbus

UPOWER_BUS_NAME = "org.freedesktop.UPower"
UPOWER_PATH = "/org/freedesktop/UPower"
UPOWER_IFACE = "org.freedesktop.UPower"
DEVICE_IFACE = "org.freedesktop.UPower.Device"
PROPS_IFACE = "org.freedesktop.DBus.Properties"

# Enum "Type" de UPower: https://upower.freedesktop.org/docs/Device.html
TYPE_NAMES = {
    0: "Desconocido",
    1: "Corriente",
    2: "Computador",
    3: "UPS",
    4: "Monitor",
    5: "Mouse",
    6: "Teclado",
    7: "PDA",
    8: "Teléfono",
    9: "Reproductor multimedia",
    10: "Tablet",
    11: "Computador",
    12: "Control de juego",
    13: "Lápiz óptico",
    14: "Touchpad",
    15: "Módem",
    16: "Red",
    17: "Audífonos (headset)",
    18: "Altavoces",
    19: "Audífonos",
    20: "Video",
    21: "Otro audio",
    22: "Control remoto",
    23: "Impresora",
    24: "Escáner",
    25: "Cámara",
    26: "Vestible",
    27: "Juguete",
    28: "Bluetooth",
}

STATE_NAMES = {
    0: "Desconocido",
    1: "Cargando",
    2: "Descargando",
    3: "Vacía",
    4: "Cargada",
    5: "Pendiente de carga",
    6: "Pendiente de descarga",
}

# Tipos de UPower que no representan una batería real (se ignoran siempre)
_TIPOS_SIN_BATERIA = {1}  # 1 = Corriente / cargador de pared


class UPowerError(RuntimeError):
    """Se lanza cuando no se puede hablar con el servicio UPower vía D-Bus."""


class UPowerClient:
    """Envuelve las llamadas D-Bus a org.freedesktop.UPower."""

    def __init__(self):
        try:
            self._bus = dbus.SystemBus()
            self._upower = self._bus.get_object(UPOWER_BUS_NAME, UPOWER_PATH)
        except dbus.DBusException as exc:
            raise UPowerError(f"No se pudo conectar a UPower: {exc}") from exc

    def list_devices(self):
        """Devuelve una lista de dicts, uno por cada dispositivo con batería real."""
        try:
            manager = dbus.Interface(self._upower, UPOWER_IFACE)
            paths = manager.EnumerateDevices()
        except dbus.DBusException as exc:
            raise UPowerError(f"No se pudo enumerar dispositivos UPower: {exc}") from exc

        dispositivos = []
        for path in paths:
            # DisplayDevice es un resumen agregado (duplica la batería principal), se omite.
            if str(path).endswith("/DisplayDevice"):
                continue
            info = self._leer_dispositivo(path)
            if info is None:
                continue
            if info["type"] in _TIPOS_SIN_BATERIA:
                continue
            if not info["is_present"]:
                continue
            dispositivos.append(info)

        dispositivos.sort(key=lambda d: d["path"])
        return dispositivos

    def _leer_dispositivo(self, path):
        try:
            obj = self._bus.get_object(UPOWER_BUS_NAME, path)
            props = dbus.Interface(obj, PROPS_IFACE)
            data = props.GetAll(DEVICE_IFACE)
        except dbus.DBusException:
            return None

        dtype = int(data.get("Type", 0))
        state = int(data.get("State", 0))
        model = str(data.get("Model") or "").strip()
        vendor = str(data.get("Vendor") or "").strip()
        nombre = model or f"{TYPE_NAMES.get(dtype, 'Dispositivo')} ({vendor})" if vendor else (model or TYPE_NAMES.get(dtype, "Dispositivo"))

        return {
            "path": str(path),
            "id": str(path).rsplit("/", 1)[-1],
            "nombre": nombre,
            "vendor": vendor,
            "type": dtype,
            "type_name": TYPE_NAMES.get(dtype, "Otro"),
            "state": state,
            "state_name": STATE_NAMES.get(state, ""),
            "is_charging": state == 1,
            "porcentaje": float(data.get("Percentage", 0.0)),
            "icon_name": str(data.get("IconName") or ""),
            "is_present": bool(data.get("IsPresent", True)),
            # Segundos hasta vaciarse / hasta completar la carga (0 = UPower aún no lo sabe).
            "tiempo_restante_seg": int(data.get("TimeToEmpty", 0)),
            "tiempo_carga_seg": int(data.get("TimeToFull", 0)),
        }
