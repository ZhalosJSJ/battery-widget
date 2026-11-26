#!/usr/bin/env python3
"""Punto de entrada de Battery Widget: widget flotante + bandeja del sistema."""

import sys

from PySide6.QtWidgets import QApplication

from app import config as config_mod
from app.widget import BatteryWidget
from app.tray import BandejaSistema, GestorNotificaciones
from app.settings_dialog import DialogoConfiguracion
from app.historial import Historial
from app.hotkey import AtajoGlobal


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = config_mod.cargar()

    historial = Historial()
    historial.purgar_antiguos(config.get("historial_dias_retencion", 7))
    app.aboutToQuit.connect(historial.cerrar)

    widget = BatteryWidget(config, historial)
    bandeja = BandejaSistema(widget, app)
    gestor_notificaciones = GestorNotificaciones(config)

    atajo = AtajoGlobal()
    atajo.activado.connect(widget._alternar_modo_mini)
    app.aboutToQuit.connect(atajo.detener)

    def aplicar_atajo():
        atajo.detener()
        if config.get("hotkey_habilitado", True):
            atajo.iniciar(config.get("hotkey_expandir", "<ctrl>+<alt>+b"))

    aplicar_atajo()

    ultimos_dispositivos = []

    def al_actualizar(dispositivos):
        nonlocal ultimos_dispositivos
        ultimos_dispositivos = dispositivos
        bandeja.actualizar_resumen(dispositivos)
        gestor_notificaciones.procesar(dispositivos, bandeja.notificar)

    def abrir_configuracion():
        dialogo = DialogoConfiguracion(config, ultimos_dispositivos, historial, parent=widget)
        if dialogo.exec():
            widget.actualizar_intervalo(config.get("poll_interval_seconds", 5))
            widget._aplicar_visibilidad_red()
            aplicar_atajo()

    widget.dispositivos_actualizados.connect(al_actualizar)
    widget.solicitar_configuracion.connect(abrir_configuracion)

    if not config.get("start_minimized", False):
        widget.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
