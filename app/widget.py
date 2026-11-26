"""Ventana flotante que muestra el nivel de batería de cada dispositivo."""

import sys

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QPoint, QRectF
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QGuiApplication
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QFrame,
    QMenu,
)

from app import adb_battery
from app import config as config_mod
from app import red as red_mod

ICONOS_POR_TIPO = {
    2: "💻",  # Computador
    11: "💻",
    17: "🎧",  # Headset
    19: "🎧",  # Audífonos
    18: "🔊",  # Altavoces
    8: "📱",  # Teléfono
    5: "🖱️",  # Mouse
    6: "⌨️",  # Teclado
    10: "📱",  # Tablet
    28: "🔵",  # Bluetooth genérico
}
ICONO_DEFAULT = "🔋"


def color_para_porcentaje(porcentaje, cargando):
    if cargando:
        return "#3b82f6"  # azul: cargando
    if porcentaje <= 10:
        return "#ef4444"  # rojo
    if porcentaje <= 25:
        return "#f97316"  # naranjo
    if porcentaje <= 50:
        return "#eab308"  # amarillo
    return "#22c55e"  # verde


def formatear_tiempo(segundos):
    """Convierte segundos a algo tipo '2h 45min'. None si aún no hay estimación."""
    if not segundos or segundos <= 0:
        return None
    segundos = int(segundos)
    horas, resto = divmod(segundos, 3600)
    minutos = resto // 60
    if horas > 0:
        return f"{horas}h {minutos:02d}min"
    return f"{minutos}min"


class FilaDispositivo(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        fila_superior = QHBoxLayout()
        self.icono_label = QLabel()
        self.nombre_label = QLabel()
        self.nombre_label.setStyleSheet("color: #e5e7eb; font-weight: 600;")
        self.porcentaje_label = QLabel()
        self.porcentaje_label.setStyleSheet("color: #e5e7eb;")
        self.porcentaje_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        fila_superior.addWidget(self.icono_label)
        fila_superior.addWidget(self.nombre_label, stretch=1)
        fila_superior.addWidget(self.porcentaje_label)
        layout.addLayout(fila_superior)

        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(8)
        layout.addWidget(self.barra)

    def actualizar(self, dispositivo):
        icono = ICONOS_POR_TIPO.get(dispositivo["type"], ICONO_DEFAULT)
        self.icono_label.setText(icono)
        nombre = dispositivo["nombre"]

        if dispositivo["porcentaje"] is None:
            # Ej: celular Android visto por USB pero aún no autorizado.
            self.nombre_label.setText(nombre)
            self.porcentaje_label.setText(dispositivo.get("state_name") or "pendiente…")
            self.barra.setValue(0)
            self.barra.setStyleSheet(
                "QProgressBar { background-color: #374151; border-radius: 4px; }"
                "QProgressBar::chunk { background-color: #6b7280; border-radius: 4px; }"
            )
            return

        estado = " (cargando)" if dispositivo["is_charging"] else ""
        self.nombre_label.setText(f"{nombre}{estado}")
        porcentaje = round(dispositivo["porcentaje"])

        if dispositivo["is_charging"]:
            tiempo = formatear_tiempo(dispositivo.get("tiempo_carga_seg"))
            sufijo = f" · {tiempo} p/cargar" if tiempo else ""
        else:
            tiempo = formatear_tiempo(dispositivo.get("tiempo_restante_seg"))
            sufijo = f" · {tiempo}" if tiempo else ""

        self.porcentaje_label.setText(f"{porcentaje}%{sufijo}")
        self.barra.setValue(porcentaje)
        color = color_para_porcentaje(porcentaje, dispositivo["is_charging"])
        self.barra.setStyleSheet(
            "QProgressBar { background-color: #374151; border-radius: 4px; }"
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}"
        )


class MiniBateria(QWidget):
    """Mini batería que se va vaciando visualmente según el % del dispositivo
    elegido (o el de menor porcentaje, si está en modo automático)."""

    dispositivo_elegido = Signal(str)  # "" = automático

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(96, 40)
        self._nombre = "Sin dispositivos"
        self._porcentaje = None
        self._cargando = False
        self._disponibles = []  # [(id, nombre)]

    def actualizar(self, dispositivo, disponibles):
        self._disponibles = disponibles
        if dispositivo is None:
            self._nombre = "Sin dispositivos"
            self._porcentaje = None
            self._cargando = False
        else:
            self._nombre = dispositivo["nombre"]
            self._porcentaje = dispositivo["porcentaje"]
            self._cargando = dispositivo["is_charging"]
        self.setToolTip(f"{self._nombre}\nClic derecho para elegir qué dispositivo mostrar aquí")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cuerpo = QRectF(4, 6, self.width() - 16, self.height() - 12)
        tapa = QRectF(cuerpo.right(), self.height() / 2 - 6, 6, 12)

        painter.setPen(QPen(QColor("#e5e7eb"), 2))
        painter.drawRoundedRect(cuerpo, 4, 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#e5e7eb"))
        painter.drawRoundedRect(tapa, 2, 2)

        if self._porcentaje is not None:
            color = color_para_porcentaje(round(self._porcentaje), self._cargando)
            ancho_relleno = max(2.0, (cuerpo.width() - 4) * (max(0, min(100, self._porcentaje)) / 100))
            relleno = QRectF(cuerpo.left() + 2, cuerpo.top() + 2, ancho_relleno, cuerpo.height() - 4)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(relleno, 2, 2)
            texto = f"{round(self._porcentaje)}%"
        else:
            texto = "—"

        painter.setPen(QPen(QColor("#f9fafb")))
        fuente = painter.font()
        fuente.setBold(True)
        fuente.setPointSize(9)
        painter.setFont(fuente)
        painter.drawText(self.rect(), Qt.AlignCenter, texto)
        painter.end()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        accion_auto = menu.addAction("Automático (el más bajo)")
        accion_auto.triggered.connect(lambda: self.dispositivo_elegido.emit(""))
        if self._disponibles:
            menu.addSeparator()
            for device_id, nombre in self._disponibles:
                accion = menu.addAction(nombre)
                accion.triggered.connect(lambda checked=False, did=device_id: self.dispositivo_elegido.emit(did))
        menu.exec(event.globalPos())


class BarrasLatencia(QWidget):
    """Barras de señal estilo "ping de videojuego": 0 a 4 barras encendidas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 20)
        self._nivel = 0
        self._color = "#6b7280"

    def actualizar(self, nivel, color):
        self._nivel = nivel
        self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        ancho_barra, espacio = 5, 2
        alturas = [6, 10, 14, 18]
        painter.setPen(Qt.NoPen)
        for i, alto in enumerate(alturas):
            x = i * (ancho_barra + espacio)
            y = self.height() - alto
            color = QColor(self._color) if i < self._nivel else QColor("#374151")
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y, ancho_barra, alto), 1, 1)
        painter.end()


class HiloTestRed(QThread):
    """Corre ping + velocidad de bajada/subida en un hilo aparte para no
    congelar la interfaz (en total puede tardar varios segundos)."""

    resultado_listo = Signal(dict)
    progreso = Signal(str)

    def run(self):
        self.progreso.emit("Midiendo latencia…")
        ping = red_mod.ejecutar_test()

        self.progreso.emit("Midiendo velocidad de bajada…")
        bajada = red_mod.medir_descarga()

        self.progreso.emit("Midiendo velocidad de subida…")
        subida = red_mod.medir_subida()

        self.resultado_listo.emit({"ping": ping, "bajada": bajada, "subida": subida})


class PanelRed(QWidget):
    """Mini panel de test de conectividad: se actualiza solo al apretar el botón."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hilo = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(6)

        separador = QFrame()
        separador.setFrameShape(QFrame.HLine)
        separador.setStyleSheet("background-color: #374151; max-height: 1px; border: none;")
        layout.addWidget(separador)

        fila = QHBoxLayout()
        titulo = QLabel("🌐 Conexión")
        titulo.setStyleSheet("color: #f9fafb; font-weight: 700; font-size: 13px;")
        fila.addWidget(titulo)
        fila.addStretch(1)

        self.boton_probar = QPushButton("Probar")
        self.boton_probar.setStyleSheet(
            "QPushButton { color: #d1d5db; background-color: #374151; border: none;"
            " border-radius: 4px; padding: 2px 10px; font-size: 12px; }"
            "QPushButton:hover { background-color: #4b5563; }"
            "QPushButton:disabled { color: #6b7280; }"
        )
        self.boton_probar.clicked.connect(self._probar)
        fila.addWidget(self.boton_probar)
        layout.addLayout(fila)

        fila_resultado = QHBoxLayout()
        self.barras = BarrasLatencia()
        fila_resultado.addWidget(self.barras)
        self.etiqueta_resultado = QLabel("Sin probar todavía")
        self.etiqueta_resultado.setStyleSheet("color: #9ca3af; font-size: 11px;")
        fila_resultado.addWidget(self.etiqueta_resultado, stretch=1)
        layout.addLayout(fila_resultado)

    def _probar(self):
        self.boton_probar.setEnabled(False)
        self.boton_probar.setText("Probando…")
        self.etiqueta_resultado.setTextFormat(Qt.PlainText)
        self.etiqueta_resultado.setText("Midiendo latencia…")
        self.etiqueta_resultado.setStyleSheet("color: #9ca3af; font-size: 11px;")
        self.barras.actualizar(0, "#6b7280")

        self._hilo = HiloTestRed(self)
        self._hilo.progreso.connect(self._mostrar_progreso)
        self._hilo.resultado_listo.connect(self._mostrar_resultado)
        self._hilo.finished.connect(self._hilo.deleteLater)
        self._hilo.start()

    def _mostrar_progreso(self, texto):
        self.etiqueta_resultado.setText(texto)
        self._ajustar_ventana()

    def _mostrar_resultado(self, resultado):
        ping = resultado["ping"]["mejor"]
        bajada = resultado["bajada"]
        subida = resultado["subida"]

        nivel, color, etiqueta = red_mod.clasificar(ping["latencia_ms"], ping["perdida_pct"])
        self.barras.actualizar(nivel, color)

        if ping["latencia_ms"] is not None:
            texto_ping = f"{etiqueta} · {round(ping['latencia_ms'])} ms"
            if ping["perdida_pct"] > 0:
                texto_ping += f" · {round(ping['perdida_pct'])}% pérdida"
        else:
            texto_ping = etiqueta

        texto_bajada = f"{bajada:.1f} Mbps" if bajada is not None else "—"
        texto_subida = f"{subida:.1f} Mbps" if subida is not None else "—"

        self.etiqueta_resultado.setTextFormat(Qt.RichText)
        self.etiqueta_resultado.setText(
            f"<span style='color:{color}; font-weight:600;'>{texto_ping}</span><br>"
            f"<span style='color:#22d3ee;'>▼ bajada: {texto_bajada}</span>"
            f"&nbsp;&nbsp;"
            f"<span style='color:#a855f7;'>▲ subida: {texto_subida}</span>"
        )
        self.etiqueta_resultado.setStyleSheet("font-size: 11px;")

        self.boton_probar.setEnabled(True)
        self.boton_probar.setText("Probar")
        self._ajustar_ventana()

    def _ajustar_ventana(self):
        ventana = self.window()
        if hasattr(ventana, "adjustSize"):
            QTimer.singleShot(0, ventana.adjustSize)


class BatteryWidget(QWidget):
    dispositivos_actualizados = Signal(list)
    solicitar_configuracion = Signal()
    solicitar_cierre = Signal()

    def __init__(self, config, historial=None):
        super().__init__()
        self.config = config
        self.historial = historial
        self._filas = {}
        self._arrastrando = False
        self._offset_arrastre = QPoint()
        self._error_mostrado = False
        self._ultimos_visibles = []
        self.modo_mini = bool(config.get("modo_mini", False))

        self.setWindowTitle("Batería de dispositivos")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(config.get("window_opacity", 0.92))

        self._construir_ui()
        self._aplicar_modo_mini(inicial=True)
        self._restaurar_posicion()

        self.cliente_upower = None
        self._inicializar_upower()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refrescar)
        self.timer.start(max(1, int(config.get("poll_interval_seconds", 5))) * 1000)
        # Se difiere al próximo ciclo del event loop para que quien construye
        # este widget alcance a conectar dispositivos_actualizados antes del
        # primer refresco (si no, ese primer chequeo de umbrales se pierde).
        QTimer.singleShot(0, self._refrescar)

    def _inicializar_upower(self):
        # UPower (D-Bus) solo existe en Linux; en cualquier otra plataforma
        # (hoy: Windows) se usa psutil para leer solo la batería del PC.
        try:
            if sys.platform.startswith("linux"):
                from app.upower import UPowerClient

                self.cliente_upower = UPowerClient()
            else:
                from app.battery_pc import ClientePCBattery

                self.cliente_upower = ClientePCBattery()
        except Exception:
            self.cliente_upower = None

    def _construir_ui(self):
        contenedor = QFrame(self)
        contenedor.setObjectName("contenedor")
        contenedor.setStyleSheet(
            "#contenedor { background-color: rgba(17, 24, 39, 235); border-radius: 12px; }"
        )
        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.addWidget(contenedor)

        self.layout_contenido = QVBoxLayout(contenedor)
        self.layout_contenido.setContentsMargins(14, 10, 14, 12)
        self.layout_contenido.setSpacing(8)

        barra_titulo = QHBoxLayout()
        titulo = QLabel("🔋 Batería")
        titulo.setStyleSheet("color: #f9fafb; font-weight: 700; font-size: 13px;")
        barra_titulo.addWidget(titulo)
        barra_titulo.addStretch(1)

        boton_buscar = QPushButton("🔄")
        boton_buscar.setToolTip("Buscar dispositivos ahora (por si acabas de conectar algo)")
        boton_buscar.setFixedSize(22, 22)
        boton_buscar.setStyleSheet(self._estilo_boton_pequeno())
        boton_buscar.clicked.connect(self._refrescar)
        barra_titulo.addWidget(boton_buscar)

        self.boton_mini = QPushButton("▭")
        self.boton_mini.setToolTip("Cambiar a modo mini / completo")
        self.boton_mini.setFixedSize(22, 22)
        self.boton_mini.setStyleSheet(self._estilo_boton_pequeno())
        self.boton_mini.clicked.connect(self._alternar_modo_mini)
        barra_titulo.addWidget(self.boton_mini)

        boton_config = QPushButton("⚙")
        boton_config.setFixedSize(22, 22)
        boton_config.setStyleSheet(self._estilo_boton_pequeno())
        boton_config.clicked.connect(self.solicitar_configuracion.emit)
        barra_titulo.addWidget(boton_config)

        boton_ocultar = QPushButton("—")
        boton_ocultar.setFixedSize(22, 22)
        boton_ocultar.setStyleSheet(self._estilo_boton_pequeno())
        boton_ocultar.clicked.connect(self.hide)
        barra_titulo.addWidget(boton_ocultar)

        self._titulo_label = titulo
        self.contenedor_titulo = QWidget()
        self.contenedor_titulo.setLayout(barra_titulo)
        self.layout_contenido.addWidget(self.contenedor_titulo)

        self.panel_dispositivos = QWidget()
        self.layout_dispositivos = QVBoxLayout(self.panel_dispositivos)
        self.layout_dispositivos.setContentsMargins(0, 0, 0, 0)
        self.layout_dispositivos.setSpacing(6)
        self.layout_contenido.addWidget(self.panel_dispositivos)

        self.mensaje_vacio = QLabel("Buscando dispositivos…")
        self.mensaje_vacio.setStyleSheet("color: #9ca3af; font-size: 11px;")
        self.layout_dispositivos.addWidget(self.mensaje_vacio)

        # En modo mini se oculta TODA la barra de título (para quedar lo más
        # chico posible) — este contenedor aparte deja solo la mini batería
        # con un botón propio para volver a tamaño completo. Configuración
        # sigue accesible desde el menú de la bandeja del sistema.
        self.contenedor_mini = QWidget()
        fila_mini = QHBoxLayout(self.contenedor_mini)
        fila_mini.setContentsMargins(0, 0, 0, 0)
        fila_mini.setSpacing(4)

        self.mini = MiniBateria()
        self.mini.dispositivo_elegido.connect(self._elegir_dispositivo_mini)
        fila_mini.addWidget(self.mini)

        self.boton_expandir_mini = QPushButton("⤢")
        self.boton_expandir_mini.setToolTip("Mostrar tamaño completo")
        self.boton_expandir_mini.setFixedSize(18, 18)
        self.boton_expandir_mini.setStyleSheet(self._estilo_boton_pequeno())
        self.boton_expandir_mini.clicked.connect(self._alternar_modo_mini)
        fila_mini.addWidget(self.boton_expandir_mini)
        fila_mini.addStretch(1)

        self.layout_contenido.addWidget(self.contenedor_mini)

        self.panel_red = PanelRed()
        self.layout_contenido.addWidget(self.panel_red)

    @staticmethod
    def _estilo_boton_pequeno():
        return (
            "QPushButton { color: #d1d5db; background-color: transparent; border: none; font-size: 13px; }"
            "QPushButton:hover { color: #ffffff; background-color: #374151; border-radius: 4px; }"
        )

    def _restaurar_posicion(self):
        pos = self.config.get("window_pos")
        if pos and isinstance(pos, (list, tuple)) and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))
        else:
            # Por defecto: pegado al extremo izquierdo de la pantalla.
            pantalla = QGuiApplication.primaryScreen()
            geometria = pantalla.availableGeometry() if pantalla else None
            x = geometria.left() if geometria else 0
            y = geometria.top() + 60 if geometria else 60
            self.move(x, y)

    def _refrescar(self):
        dispositivos = []
        if self.cliente_upower is not None:
            try:
                dispositivos = self.cliente_upower.list_devices()
                self._error_mostrado = False
            except Exception:
                if not self._error_mostrado:
                    self.mensaje_vacio.setText("No se pudo leer el estado de la batería.")
                    self.mensaje_vacio.show()
                    self._error_mostrado = True
                return
        else:
            self._inicializar_upower()
            if self.cliente_upower is None:
                self.mensaje_vacio.setText("UPower no disponible en este sistema.")
                self.mensaje_vacio.show()
                return

        if self.config.get("adb_enabled", True):
            try:
                dispositivos += adb_battery.listar_dispositivos_android()
            except Exception:
                # Un celular Android por USB es un extra opcional: si falla
                # por lo que sea, no debe tumbar la actualización del resto.
                pass

        ocultos = set(self.config.get("hidden_devices", []))
        visibles = [d for d in dispositivos if d["id"] not in ocultos]

        if not visibles:
            self.mensaje_vacio.setText("Sin dispositivos con batería detectados.")
            self.mensaje_vacio.show()
        else:
            self.mensaje_vacio.hide()

        ids_actuales = {d["id"] for d in visibles}
        for id_obsoleto in list(self._filas.keys()):
            if id_obsoleto not in ids_actuales:
                fila = self._filas.pop(id_obsoleto)
                self.layout_dispositivos.removeWidget(fila)
                fila.deleteLater()

        for dispositivo in visibles:
            fila = self._filas.get(dispositivo["id"])
            if fila is None:
                fila = FilaDispositivo(self)
                self.layout_dispositivos.addWidget(fila)
                self._filas[dispositivo["id"]] = fila
            fila.actualizar(dispositivo)

        self._ultimos_visibles = visibles
        self._actualizar_mini(visibles)

        if self.historial is not None:
            try:
                self.historial.registrar(dispositivos)
            except Exception:
                pass  # el historial es un extra: nunca debe tumbar el refresco

        self._ajustar_tamano_diferido()
        self.dispositivos_actualizados.emit(dispositivos)

    def actualizar_intervalo(self, segundos):
        self.timer.start(max(1, int(segundos)) * 1000)

    # --- modo mini ---
    def _alternar_modo_mini(self):
        self.modo_mini = not self.modo_mini
        self.config["modo_mini"] = self.modo_mini
        config_mod.guardar(self.config)
        self._aplicar_modo_mini()

    def _aplicar_modo_mini(self, inicial=False):
        self.contenedor_titulo.setVisible(not self.modo_mini)
        self.panel_dispositivos.setVisible(not self.modo_mini)
        self.contenedor_mini.setVisible(self.modo_mini)
        self.setMinimumWidth(60 if self.modo_mini else 230)
        self._aplicar_visibilidad_red(ajustar_tamano=False)
        if not inicial:
            self._ajustar_tamano_diferido()

    def _aplicar_visibilidad_red(self, ajustar_tamano=True):
        # El panel de conectividad no tiene sentido en modo mini (se apunta a
        # que ese modo quede lo más chico posible).
        mostrar = bool(self.config.get("mostrar_test_red", False)) and not self.modo_mini
        self.panel_red.setVisible(mostrar)
        if ajustar_tamano:
            self._ajustar_tamano_diferido()

    def _ajustar_tamano_diferido(self):
        # Qt recalcula el layout de forma diferida tras un setVisible(): si se
        # llama adjustSize() en el mismo tick, mide con el tamaño viejo (por
        # eso hacía falta apretar el botón dos veces). Se difiere al próximo
        # ciclo del event loop, cuando el layout ya está al día.
        QTimer.singleShot(0, self.adjustSize)

    def _elegir_dispositivo_mini(self, device_id):
        self.config["dispositivo_mini"] = device_id or None
        config_mod.guardar(self.config)
        self._actualizar_mini(self._ultimos_visibles)

    def _actualizar_mini(self, visibles):
        con_datos = [d for d in visibles if d["porcentaje"] is not None]
        elegido_id = self.config.get("dispositivo_mini")
        dispositivo = None
        if elegido_id:
            dispositivo = next((d for d in con_datos if d["id"] == elegido_id), None)
        if dispositivo is None and con_datos:
            dispositivo = min(con_datos, key=lambda d: d["porcentaje"])
        disponibles = [(d["id"], d["nombre"]) for d in visibles]
        self.mini.actualizar(dispositivo, disponibles)

    def guardar_posicion(self):
        pos = self.pos()
        self.config["window_pos"] = [pos.x(), pos.y()]

    # --- arrastre de la ventana sin bordes ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._arrastrando = True
            self._offset_arrastre = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._arrastrando and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._offset_arrastre)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._arrastrando:
            self._arrastrando = False
            self.guardar_posicion()

    def closeEvent(self, event):
        self.guardar_posicion()
        event.ignore()
        self.hide()
