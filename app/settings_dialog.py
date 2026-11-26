"""Diálogo de configuración: umbrales de aviso, intervalo, autoarranque y dispositivos visibles."""

import sys
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QGroupBox,
    QScrollArea,
    QWidget,
    QMessageBox,
    QComboBox,
)

from app import config as config_mod

DURACIONES_NO_MOLESTAR = {
    "Indefinido (hasta desactivarlo)": None,
    "1 hora": 3600,
    "4 horas": 4 * 3600,
    "8 horas": 8 * 3600,
}

_NOMBRES_MODIFICADOR = {"<ctrl>": "Ctrl", "<alt>": "Alt", "<shift>": "Shift", "<cmd>": "Super"}


def _texto_visible_desde_pynput(combinacion):
    """'<ctrl>+<alt>+b' -> 'Ctrl+Alt+B' (para mostrarlo en el campo)."""
    if not combinacion:
        return ""
    partes = []
    for parte in combinacion.split("+"):
        if parte in _NOMBRES_MODIFICADOR:
            partes.append(_NOMBRES_MODIFICADOR[parte])
        elif parte.startswith("<f") and parte.endswith(">"):
            partes.append(parte[1:-1].upper())
        else:
            partes.append(parte.upper())
    return "+".join(partes)


class CapturaAtajo(QLineEdit):
    """Campo de solo lectura: al escribirle, graba la próxima combinación de
    teclas que se presione (mientras el diálogo tiene el foco) y la
    convierte al formato que espera pynput para el atajo global."""

    combinacion_capturada = Signal(str, str)  # (formato pynput, texto visible)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Clic aquí y presiona la combinación…")

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta, Qt.Key_AltGr):
            return  # esperamos a que se presione también una tecla "normal"

        modificadores = event.modifiers()
        partes_pynput = []
        partes_visibles = []
        if modificadores & Qt.ControlModifier:
            partes_pynput.append("<ctrl>")
            partes_visibles.append("Ctrl")
        if modificadores & Qt.AltModifier:
            partes_pynput.append("<alt>")
            partes_visibles.append("Alt")
        if modificadores & Qt.ShiftModifier:
            partes_pynput.append("<shift>")
            partes_visibles.append("Shift")
        if modificadores & Qt.MetaModifier:
            partes_pynput.append("<cmd>")
            partes_visibles.append("Super")

        es_funcion = Qt.Key_F1 <= key <= Qt.Key_F35
        if not partes_pynput and not es_funcion:
            # Sin modificador y sin ser una tecla de función: se ignora para
            # no terminar capturando una tecla normal de tipeo (rompería
            # escribir esa letra en cualquier otra parte del sistema).
            return

        if es_funcion:
            numero = key - Qt.Key_F1 + 1
            tecla_pynput = f"<f{numero}>"
            tecla_visible = f"F{numero}"
        else:
            texto = event.text().strip()
            if not texto:
                nombre = QKeySequence(key).toString()
                if not nombre:
                    return
                texto = nombre
            tecla_pynput = texto.lower()
            tecla_visible = texto.upper()

        partes_pynput.append(tecla_pynput)
        partes_visibles.append(tecla_visible)

        pynput_str = "+".join(partes_pynput)
        visible_str = "+".join(partes_visibles)
        self.setText(visible_str)
        self.combinacion_capturada.emit(pynput_str, visible_str)


class DialogoConfiguracion(QDialog):
    def __init__(self, config, dispositivos_conocidos, historial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración — Battery Widget")
        self.setMinimumWidth(360)
        self.config = config
        self.historial = historial
        self.dispositivos_conocidos = dispositivos_conocidos
        self._checks_dispositivos = {}

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.campo_umbrales = QLineEdit(", ".join(str(u) for u in sorted(set(config.get("thresholds", [])), reverse=True)))
        self.campo_umbrales.setPlaceholderText("Ej: 50, 25, 10")
        form.addRow("Avisar en (%):", self.campo_umbrales)

        self.spin_intervalo = QSpinBox()
        self.spin_intervalo.setRange(1, 300)
        self.spin_intervalo.setSuffix(" s")
        self.spin_intervalo.setValue(int(config.get("poll_interval_seconds", 5)))
        form.addRow("Intervalo de actualización:", self.spin_intervalo)

        layout.addLayout(form)

        self.check_full = QCheckBox("Avisar cuando un dispositivo llegue a carga completa (100%)")
        self.check_full.setChecked(bool(config.get("notify_full_charge", True)))
        layout.addWidget(self.check_full)

        self.check_adb = QCheckBox("Buscar celular Android conectado por USB (requiere ADB y depuración USB)")
        self.check_adb.setChecked(bool(config.get("adb_enabled", True)))
        layout.addWidget(self.check_adb)

        self.check_autostart = QCheckBox("Iniciar automáticamente al iniciar sesión")
        self.check_autostart.setChecked(config_mod.autostart_activo())
        layout.addWidget(self.check_autostart)

        self.check_test_red = QCheckBox("🌐 Mostrar test de conectividad (bajo el widget de batería)")
        self.check_test_red.setChecked(bool(config.get("mostrar_test_red", False)))
        layout.addWidget(self.check_test_red)

        grupo_mini = QGroupBox("Modo mini")
        form_mini = QFormLayout(grupo_mini)
        self.combo_dispositivo_mini = QComboBox()
        self.combo_dispositivo_mini.addItem("Automático (el más bajo)", None)
        elegido_actual = config.get("dispositivo_mini")
        for d in dispositivos_conocidos:
            self.combo_dispositivo_mini.addItem(d["nombre"], d["id"])
        if elegido_actual:
            indice = self.combo_dispositivo_mini.findData(elegido_actual)
            if indice >= 0:
                self.combo_dispositivo_mini.setCurrentIndex(indice)
        form_mini.addRow("Dispositivo a priorizar:", self.combo_dispositivo_mini)
        layout.addWidget(grupo_mini)

        grupo_dnd = QGroupBox("🔕 No molestar")
        layout_dnd = QVBoxLayout(grupo_dnd)
        self.check_no_molestar = QCheckBox("Pausar avisos de batería")
        self.check_no_molestar.setChecked(bool(config.get("no_molestar_activo", False)))
        layout_dnd.addWidget(self.check_no_molestar)
        fila_duracion = QHBoxLayout()
        fila_duracion.addWidget(QLabel("Duración:"))
        self.combo_duracion_dnd = QComboBox()
        self.combo_duracion_dnd.addItems(list(DURACIONES_NO_MOLESTAR.keys()))
        fila_duracion.addWidget(self.combo_duracion_dnd, stretch=1)
        layout_dnd.addLayout(fila_duracion)
        layout.addWidget(grupo_dnd)

        grupo_atajo = QGroupBox("⌨ Atajo de teclado (global)")
        layout_atajo = QVBoxLayout(grupo_atajo)
        self.check_atajo = QCheckBox("Activar atajo para pasar a mini / tamaño completo")
        self.check_atajo.setChecked(bool(config.get("hotkey_habilitado", True)))
        layout_atajo.addWidget(self.check_atajo)

        self._atajo_pynput = config.get("hotkey_expandir", "<ctrl>+<alt>+b")
        self.campo_atajo = CapturaAtajo()
        self.campo_atajo.setText(_texto_visible_desde_pynput(self._atajo_pynput))
        self.campo_atajo.combinacion_capturada.connect(self._al_capturar_atajo)
        layout_atajo.addWidget(self.campo_atajo)

        ayuda_atajo = QLabel("Funciona aunque la app no tenga el foco (requiere sesión X11 en Linux).")
        ayuda_atajo.setStyleSheet("color: #9ca3af; font-size: 10px;")
        ayuda_atajo.setWordWrap(True)
        layout_atajo.addWidget(ayuda_atajo)
        layout.addWidget(grupo_atajo)

        if self.historial is not None:
            boton_historial = QPushButton("📈 Ver historial de batería")
            boton_historial.clicked.connect(self._abrir_historial)
            layout.addWidget(boton_historial)

        grupo_dispositivos = QGroupBox("Dispositivos visibles")
        layout_grupo = QVBoxLayout(grupo_dispositivos)
        contenedor_scroll = QWidget()
        layout_scroll = QVBoxLayout(contenedor_scroll)
        ocultos = set(config.get("hidden_devices", []))

        if not dispositivos_conocidos:
            layout_scroll.addWidget(QLabel("Aún no se detectan dispositivos."))
        for d in dispositivos_conocidos:
            check = QCheckBox(d["nombre"])
            check.setChecked(d["id"] not in ocultos)
            self._checks_dispositivos[d["id"]] = check
            layout_scroll.addWidget(check)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(contenedor_scroll)
        scroll.setMaximumHeight(160)
        layout_grupo.addWidget(scroll)
        layout.addWidget(grupo_dispositivos)

        grupo_umbrales = QGroupBox("Umbrales personalizados por dispositivo")
        layout_grupo_umb = QVBoxLayout(grupo_umbrales)
        contenedor_umb = QWidget()
        layout_umb = QVBoxLayout(contenedor_umb)
        overrides = config.get("device_thresholds", {})
        self._filas_umbral = {}

        if not dispositivos_conocidos:
            layout_umb.addWidget(QLabel("Aún no se detectan dispositivos."))
        for d in dispositivos_conocidos:
            fila = QHBoxLayout()
            fila.addWidget(QLabel(d["nombre"]), stretch=1)
            check_personalizar = QCheckBox("Personalizar")
            campo_propio = QLineEdit()
            campo_propio.setPlaceholderText("Ej: 60, 30, 15")
            campo_propio.setMaximumWidth(120)
            valores_propios = overrides.get(d["id"])
            if valores_propios:
                check_personalizar.setChecked(True)
                campo_propio.setText(", ".join(str(u) for u in sorted(set(valores_propios), reverse=True)))
            campo_propio.setEnabled(check_personalizar.isChecked())
            check_personalizar.toggled.connect(campo_propio.setEnabled)
            fila.addWidget(check_personalizar)
            fila.addWidget(campo_propio)
            fila_widget = QWidget()
            fila_widget.setLayout(fila)
            layout_umb.addWidget(fila_widget)
            self._filas_umbral[d["id"]] = (check_personalizar, campo_propio, d["nombre"])

        scroll_umb = QScrollArea()
        scroll_umb.setWidgetResizable(True)
        scroll_umb.setWidget(contenedor_umb)
        scroll_umb.setMaximumHeight(140)
        layout_grupo_umb.addWidget(scroll_umb)
        layout.addWidget(grupo_umbrales)

        botones = QHBoxLayout()
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setDefault(True)
        boton_guardar.clicked.connect(self._guardar)
        botones.addStretch(1)
        botones.addWidget(boton_cancelar)
        botones.addWidget(boton_guardar)
        layout.addLayout(botones)

    def _parsear_umbrales(self, texto, etiqueta):
        """Convierte 'Ej: 60, 30, 15' en [60, 30, 15], o None + aviso si algo no es válido."""
        umbrales = []
        for parte in texto.split(","):
            parte = parte.strip()
            if not parte:
                continue
            try:
                valor = int(parte)
            except ValueError:
                QMessageBox.warning(self, "Valor inválido", f"En «{etiqueta}»: '{parte}' no es un número válido de porcentaje.")
                return None
            if not (0 <= valor <= 100):
                QMessageBox.warning(self, "Valor inválido", f"En «{etiqueta}»: los porcentajes deben estar entre 0 y 100.")
                return None
            umbrales.append(valor)
        return umbrales

    def _guardar(self):
        umbrales = self._parsear_umbrales(self.campo_umbrales.text().strip(), "Avisar en (%)")
        if umbrales is None:
            return

        device_thresholds = {}
        for device_id, (check, campo, nombre) in self._filas_umbral.items():
            if not check.isChecked():
                continue
            valores = self._parsear_umbrales(campo.text().strip(), f"Umbrales de {nombre}")
            if valores is None:
                return
            if valores:
                device_thresholds[device_id] = sorted(set(valores), reverse=True)

        self.config["thresholds"] = sorted(set(umbrales), reverse=True) or [50, 25, 10]
        self.config["device_thresholds"] = device_thresholds
        self.config["poll_interval_seconds"] = self.spin_intervalo.value()
        self.config["notify_full_charge"] = self.check_full.isChecked()
        self.config["adb_enabled"] = self.check_adb.isChecked()
        self.config["mostrar_test_red"] = self.check_test_red.isChecked()
        self.config["dispositivo_mini"] = self.combo_dispositivo_mini.currentData()
        self.config["hotkey_habilitado"] = self.check_atajo.isChecked()
        self.config["hotkey_expandir"] = self._atajo_pynput

        self.config["no_molestar_activo"] = self.check_no_molestar.isChecked()
        if self.check_no_molestar.isChecked():
            duracion_seg = DURACIONES_NO_MOLESTAR[self.combo_duracion_dnd.currentText()]
            self.config["no_molestar_hasta_ts"] = (time.time() + duracion_seg) if duracion_seg else None
        else:
            self.config["no_molestar_hasta_ts"] = None

        ocultos = [id_ for id_, check in self._checks_dispositivos.items() if not check.isChecked()]
        self.config["hidden_devices"] = ocultos

        config_mod.set_autostart(self.check_autostart.isChecked(), self._comando_lanzador())

        config_mod.guardar(self.config)
        self.accept()

    def _al_capturar_atajo(self, pynput_str, visible_str):
        self._atajo_pynput = pynput_str

    def _abrir_historial(self):
        from app.historial_dialog import DialogoHistorial

        dispositivo_sugerido = self.combo_dispositivo_mini.currentData()
        dialogo = DialogoHistorial(self.historial, dispositivo_sugerido, parent=self)
        dialogo.exec()

    @staticmethod
    def _comando_lanzador():
        # Empaquetado con PyInstaller: sys.executable YA es la app, sin script aparte.
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        return f'"{sys.executable}" "{DialogoConfiguracion._ruta_main()}"'

    @staticmethod
    def _ruta_main():
        import os

        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
