"""Lectura de la batería propia del computador, multiplataforma (vía psutil).

En Linux se prefiere UPower (más rico: además del PC ve Bluetooth y otros
periféricos) — este módulo es el que se usa en plataformas sin UPower
(hoy en día, Windows).
"""

import psutil

ESTADO_DESCARGANDO = 2
ESTADO_CARGANDO = 1


class BateriaPCNoDisponibleError(RuntimeError):
    """El equipo no reporta batería (ej: computador de escritorio sin UPS)."""


class ClientePCBattery:
    """Misma interfaz que UPowerClient: expone list_devices(). Solo entrega
    la batería del propio computador (sin Bluetooth ni otros periféricos)."""

    def list_devices(self):
        info = psutil.sensors_battery()
        if info is None:
            raise BateriaPCNoDisponibleError(
                "Este equipo no reporta batería (¿computador de escritorio?)."
            )

        cargando = bool(info.power_plugged) and info.percent < 100

        tiempo_restante = 0
        secsleft = getattr(info, "secsleft", None)
        no_disponibles = {
            getattr(psutil, "POWER_TIME_UNLIMITED", -1),
            getattr(psutil, "POWER_TIME_UNKNOWN", -2),
        }
        if not info.power_plugged and secsleft is not None and secsleft not in no_disponibles:
            tiempo_restante = int(secsleft)

        return [
            {
                "path": "pc:local",
                "id": "pc_local",
                "nombre": "Este computador",
                "vendor": "",
                "type": 2,  # Computador
                "type_name": "Computador",
                "state": ESTADO_CARGANDO if cargando else ESTADO_DESCARGANDO,
                "state_name": "Cargando" if cargando else "Descargando",
                "is_charging": cargando,
                "porcentaje": float(info.percent),
                "icon_name": "",
                "is_present": True,
                "tiempo_restante_seg": tiempo_restante,
                # psutil no entrega una estimación de tiempo hasta completar la carga.
                "tiempo_carga_seg": 0,
            }
        ]
