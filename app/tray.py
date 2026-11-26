"""Icono de bandeja del sistema y lógica de notificaciones por umbral de batería."""

import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

from app import config as config_mod

if sys.platform.startswith("linux"):
    import dbus
else:
    # dbus-python es específico de Linux; en otras plataformas (Windows) se
    # usa directo QSystemTrayIcon.showMessage(), que ahí sí funciona nativo.
    dbus = None

NOTIFY_BUS_NAME = "org.freedesktop.Notifications"
NOTIFY_PATH = "/org/freedesktop/Notifications"
NOTIFY_IFACE = "org.freedesktop.Notifications"
NOTIFY_EXPIRE_MS = 8000


def _generar_icono(color="#22c55e"):
    """Dibuja un ícono de batería simple (no depende de un tema de íconos instalado)."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setPen(QPen(QColor("#e5e7eb"), 4))
    painter.setBrush(QBrush(QColor(color)))
    painter.drawRoundedRect(6, 16, 46, 32, 6, 6)
    painter.setBrush(QBrush(QColor("#e5e7eb")))
    painter.drawRoundedRect(52, 26, 6, 12, 2, 2)

    painter.end()
    return QIcon(pixmap)


def no_molestar_activo(config):
    """True si el modo No Molestar está activo. Si tenía una duración fijada
    y ya expiró, lo desactiva solo (y persiste el cambio)."""
    if not config.get("no_molestar_activo", False):
        return False
    hasta_ts = config.get("no_molestar_hasta_ts")
    if hasta_ts is not None and time.time() >= hasta_ts:
        config["no_molestar_activo"] = False
        config["no_molestar_hasta_ts"] = None
        config_mod.guardar(config)
        return False
    return True


class GestorNotificaciones:
    """Decide cuándo avisar que un dispositivo cruzó un umbral de batería configurado,
    cuándo apareció un dispositivo nunca antes visto, y respeta el modo No Molestar."""

    def __init__(self, config):
        self.config = config
        self._estado = {}
        self._conocidos = set(config.get("dispositivos_conocidos", []))
        self._primera_pasada = True

    def procesar(self, dispositivos, callback_notificar):
        self._detectar_nuevos(dispositivos, callback_notificar)

        if no_molestar_activo(self.config):
            return

        thresholds_globales = sorted(set(int(u) for u in self.config.get("thresholds", [])))
        overrides = self.config.get("device_thresholds", {})
        hysteresis = float(self.config.get("hysteresis", 5))
        notificar_full = self.config.get("notify_full_charge", True)

        for d in dispositivos:
            if d["porcentaje"] is None:
                continue  # ej: celular visto por USB pero aún no autorizado por adb

            propios = overrides.get(d["id"])
            thresholds = sorted(set(int(u) for u in propios)) if propios else thresholds_globales

            estado = self._estado.setdefault(d["id"], {"ultimo_umbral": None, "avisado_full": False})
            porcentaje = d["porcentaje"]

            if d["is_charging"]:
                estado["ultimo_umbral"] = None
                if notificar_full and porcentaje >= 99.5 and not estado["avisado_full"]:
                    callback_notificar(f"🔌 {d['nombre']}", "Carga completa (100%).")
                    estado["avisado_full"] = True
                if porcentaje < 95:
                    estado["avisado_full"] = False
                continue

            estado["avisado_full"] = False

            # Si subió bastante desde el último aviso, se permite volver a avisar más adelante.
            if estado["ultimo_umbral"] is not None and porcentaje > estado["ultimo_umbral"] + hysteresis:
                estado["ultimo_umbral"] = None

            candidatos = [u for u in thresholds if porcentaje <= u]
            umbral_actual = min(candidatos) if candidatos else None

            if umbral_actual is not None and (
                estado["ultimo_umbral"] is None or umbral_actual < estado["ultimo_umbral"]
            ):
                callback_notificar(
                    f"🔋 {d['nombre']}: {umbral_actual}% o menos",
                    f"Quedan {round(porcentaje)}% de batería.",
                )
                estado["ultimo_umbral"] = umbral_actual

    def _detectar_nuevos(self, dispositivos, callback_notificar):
        """Avisa la primera vez que aparece un dispositivo nunca antes visto.
        En la primera pasada (recién abierta la app) solo arma la lista base,
        sin avisar de lo que ya estaba conectado al partir."""
        ids_actuales = {d["id"] for d in dispositivos}
        nuevos = ids_actuales - self._conocidos

        if self._primera_pasada:
            self._conocidos |= ids_actuales
            self._primera_pasada = False
            self._guardar_conocidos()
            return

        if not nuevos:
            return

        for d in dispositivos:
            if d["id"] in nuevos:
                callback_notificar("🆕 Dispositivo detectado", f"{d['nombre']} ya se está monitoreando.")
        self._conocidos |= nuevos
        self._guardar_conocidos()

    def _guardar_conocidos(self):
        self.config["dispositivos_conocidos"] = sorted(self._conocidos)
        config_mod.guardar(self.config)


class BandejaSistema(QSystemTrayIcon):
    def __init__(self, widget, app):
        super().__init__(_generar_icono(), app)
        self.widget = widget
        self.app = app
        self.setToolTip("Battery Widget")

        menu = QMenu()
        self.accion_mostrar = menu.addAction("Mostrar/Ocultar widget")
        self.accion_mostrar.triggered.connect(self._alternar_widget)
        self.accion_config = menu.addAction("Configuración…")
        self.accion_config.triggered.connect(widget.solicitar_configuracion.emit)
        menu.addSeparator()
        self.accion_salir = menu.addAction("Salir")
        self.accion_salir.triggered.connect(app.quit)

        self.setContextMenu(menu)
        self.activated.connect(self._al_activar)
        self.setVisible(True)

        self._notify_iface = self._conectar_notificaciones()

    @staticmethod
    def _conectar_notificaciones():
        # QSystemTrayIcon.showMessage() no funciona en todos los entornos de
        # Linux (p. ej. bandejas "heredadas" de XFCE): ahí se llama directo
        # al servicio de notificaciones vía D-Bus, lo mismo que usa
        # `notify-send`. En Windows no aplica: showMessage() ya es nativo.
        if dbus is None:
            return None
        try:
            bus = dbus.SessionBus()
            proxy = bus.get_object(NOTIFY_BUS_NAME, NOTIFY_PATH)
            return dbus.Interface(proxy, NOTIFY_IFACE)
        except dbus.DBusException:
            return None

    def _alternar_widget(self):
        if self.widget.isVisible():
            self.widget.guardar_posicion()
            self.widget.hide()
        else:
            self.widget.show()
            self.widget.raise_()
            self.widget.activateWindow()

    def _al_activar(self, razon):
        if razon == QSystemTrayIcon.Trigger:
            self._alternar_widget()

    def actualizar_resumen(self, dispositivos):
        if not dispositivos:
            self.setToolTip("Battery Widget — sin dispositivos detectados")
            return
        partes = [
            f"{d['nombre']}: {round(d['porcentaje'])}%" if d["porcentaje"] is not None else f"{d['nombre']}: {d.get('state_name') or 'pendiente'}"
            for d in dispositivos
        ]
        self.setToolTip("Battery Widget\n" + "\n".join(partes))

    def notificar(self, titulo, mensaje):
        if self._notify_iface is not None:
            try:
                self._notify_iface.Notify(
                    "Battery Widget", 0, "", titulo, mensaje, [], {}, NOTIFY_EXPIRE_MS
                )
                return
            except dbus.DBusException:
                pass
        # Respaldo si no hay servicio de notificaciones por D-Bus disponible.
        self.showMessage(titulo, mensaje, QSystemTrayIcon.Information, NOTIFY_EXPIRE_MS)
