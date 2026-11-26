"""Diálogo con el historial gráfico de batería (gráfico dibujado a mano, sin
dependencias extra como matplotlib)."""

import time

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QWidget,
)

RANGOS = {
    "Últimas 6 horas": 6 * 3600,
    "Últimas 24 horas": 24 * 3600,
    "Últimos 7 días": 7 * 24 * 3600,
}


class GraficoHistorial(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 220)
        self._puntos = []  # [(ts, porcentaje, is_charging)]
        self._desde_ts = 0
        self._hasta_ts = 0

    def set_datos(self, puntos, desde_ts, hasta_ts):
        self._puntos = puntos
        self._desde_ts = desde_ts
        self._hasta_ts = max(hasta_ts, desde_ts + 1)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111827"))

        margen_izq, margen_der, margen_arriba, margen_abajo = 38, 14, 14, 26
        ancho = self.width() - margen_izq - margen_der
        alto = self.height() - margen_arriba - margen_abajo
        if ancho <= 0 or alto <= 0:
            painter.end()
            return

        area = QRectF(margen_izq, margen_arriba, ancho, alto)

        # Líneas guía horizontales (0/25/50/75/100%)
        painter.setPen(QPen(QColor("#374151"), 1))
        font_pequena = QFont()
        font_pequena.setPointSize(8)
        painter.setFont(font_pequena)
        for pct in (0, 25, 50, 75, 100):
            y = area.top() + area.height() * (1 - pct / 100)
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(QPen(QColor("#9ca3af")))
            painter.drawText(QRectF(0, y - 8, margen_izq - 4, 16), Qt.AlignRight | Qt.AlignVCenter, f"{pct}")
            painter.setPen(QPen(QColor("#374151"), 1))

        if not self._puntos:
            painter.setPen(QPen(QColor("#9ca3af")))
            painter.drawText(area, Qt.AlignCenter, "Sin datos en este rango todavía.")
            painter.end()
            return

        rango_seg = max(1, self._hasta_ts - self._desde_ts)

        def x_de(ts):
            return area.left() + (ts - self._desde_ts) / rango_seg * area.width()

        def y_de(pct):
            return area.top() + area.height() * (1 - max(0, min(100, pct)) / 100)

        # Relleno bajo la curva
        ruta_rellena = [QPointF(x_de(self._puntos[0][0]), area.bottom())]
        for ts, pct, _ in self._puntos:
            ruta_rellena.append(QPointF(x_de(ts), y_de(pct)))
        ruta_rellena.append(QPointF(x_de(self._puntos[-1][0]), area.bottom()))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(59, 130, 246, 60))
        painter.drawPolygon(ruta_rellena)

        # Línea principal; en tramos cargando se pinta azul, si no, verde/rojo según nivel.
        for i in range(1, len(self._puntos)):
            ts0, pct0, cargando0 = self._puntos[i - 1]
            ts1, pct1, _ = self._puntos[i]
            color = "#3b82f6" if cargando0 else ("#ef4444" if pct0 <= 20 else "#22c55e")
            painter.setPen(QPen(QColor(color), 2))
            painter.drawLine(QPointF(x_de(ts0), y_de(pct0)), QPointF(x_de(ts1), y_de(pct1)))

        # Etiquetas de tiempo en el eje X (inicio, medio, fin)
        painter.setPen(QPen(QColor("#9ca3af")))
        for frac in (0.0, 0.5, 1.0):
            ts = self._desde_ts + rango_seg * frac
            etiqueta = time.strftime("%H:%M", time.localtime(ts))
            x = x_de(ts)
            alineacion = Qt.AlignLeft if frac == 0 else (Qt.AlignRight if frac == 1 else Qt.AlignHCenter)
            painter.drawText(QRectF(x - 40, area.bottom() + 4, 80, 16), alineacion | Qt.AlignVCenter, etiqueta)

        painter.end()


class DialogoHistorial(QDialog):
    def __init__(self, historial, dispositivo_id_sugerido=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historial de batería")
        self.setMinimumSize(480, 320)
        self.historial = historial

        layout = QVBoxLayout(self)

        controles = QHBoxLayout()
        controles.addWidget(QLabel("Dispositivo:"))
        self.combo_dispositivo = QComboBox()
        self._dispositivos = self.historial.dispositivos_con_historial()
        for device_id, device_name in self._dispositivos:
            self.combo_dispositivo.addItem(device_name, device_id)
        controles.addWidget(self.combo_dispositivo, stretch=1)

        controles.addWidget(QLabel("Rango:"))
        self.combo_rango = QComboBox()
        self.combo_rango.addItems(list(RANGOS.keys()))
        controles.addWidget(self.combo_rango)

        boton_actualizar = QPushButton("Actualizar")
        boton_actualizar.clicked.connect(self._actualizar_grafico)
        controles.addWidget(boton_actualizar)

        layout.addLayout(controles)

        self.grafico = GraficoHistorial()
        layout.addWidget(self.grafico, stretch=1)

        if not self._dispositivos:
            self.grafico.set_datos([], time.time() - 3600, time.time())
        else:
            if dispositivo_id_sugerido:
                indice = self.combo_dispositivo.findData(dispositivo_id_sugerido)
                if indice >= 0:
                    self.combo_dispositivo.setCurrentIndex(indice)
            self._actualizar_grafico()

        self.combo_dispositivo.currentIndexChanged.connect(self._actualizar_grafico)
        self.combo_rango.currentIndexChanged.connect(self._actualizar_grafico)

    def _actualizar_grafico(self):
        if not self._dispositivos:
            return
        device_id = self.combo_dispositivo.currentData()
        ventana_seg = RANGOS[self.combo_rango.currentText()]
        hasta_ts = time.time()
        desde_ts = hasta_ts - ventana_seg
        puntos = self.historial.leer(device_id, desde_ts)
        self.grafico.set_datos(puntos, desde_ts, hasta_ts)
