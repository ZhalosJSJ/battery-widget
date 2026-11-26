"""Atajo de teclado global (funciona aunque la app no tenga el foco) para
mostrar/ocultar el modo mini. Usa `pynput`, que en Linux escucha eventos de
teclado vía X11 (requiere sesión X11; puede no funcionar bajo Wayland puro)
y en Windows vía los hooks nativos del sistema."""

from PySide6.QtCore import QObject, Signal

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

MODIFICADORES_VALIDOS = ("<ctrl>", "<alt>", "<shift>", "<cmd>")

_MODIFICADORES_PYNPUT = {}
if keyboard is not None:
    _MODIFICADORES_PYNPUT = {
        "<ctrl>": keyboard.Key.ctrl,
        "<alt>": keyboard.Key.alt,
        "<shift>": keyboard.Key.shift,
        "<cmd>": keyboard.Key.cmd,
    }


def combinacion_valida(combinacion):
    """Exige al menos un modificador, salvo que sea una tecla de función sola
    (F1-F24) — así no se puede pisar por accidente una tecla normal de tipeo."""
    if not combinacion:
        return False
    partes = combinacion.split("+")
    tiene_modificador = any(p in MODIFICADORES_VALIDOS for p in partes)
    es_funcion_sola = len(partes) == 1 and partes[0].startswith("<f") and partes[0].endswith(">")
    return tiene_modificador or es_funcion_sola


def _parsear_combinacion(combinacion):
    """'<ctrl>+<alt>+b' -> {Key.ctrl, Key.alt, KeyCode.from_char('b')} (o None si algo no se reconoce)."""
    teclas = set()
    for parte in combinacion.split("+"):
        parte = parte.strip()
        if parte in _MODIFICADORES_PYNPUT:
            teclas.add(_MODIFICADORES_PYNPUT[parte])
        elif parte.startswith("<f") and parte.endswith(">") and parte[2:-1].isdigit():
            tecla_funcion = getattr(keyboard.Key, parte[1:-1], None)
            if tecla_funcion is None:
                return None
            teclas.add(tecla_funcion)
        elif len(parte) == 1:
            teclas.add(keyboard.KeyCode.from_char(parte))
        else:
            return None
    return teclas or None


class AtajoGlobal(QObject):
    """Escucha teclado global con pynput y detecta cuándo están todas las
    teclas de la combinación presionadas al mismo tiempo. Se lleva un `set`
    propio de teclas presionadas en vez de usar pynput.GlobalHotKeys
    directamente, porque es más tolerante a eventos de teclado duplicados
    (un `set` ignora sin problema una tecla que ya estaba agregada).

    La señal `activado` se puede conectar directo a un slot de Qt: aunque
    pynput dispara el callback en su propio hilo, Qt encola la entrega en el
    hilo principal automáticamente."""

    activado = Signal()

    def __init__(self):
        super().__init__()
        self._listener = None
        self._teclas_objetivo = None
        self._teclas_presionadas = set()

    def disponible(self):
        return keyboard is not None

    def iniciar(self, combinacion):
        self.detener()
        if keyboard is None or not combinacion_valida(combinacion):
            return False
        teclas_objetivo = _parsear_combinacion(combinacion)
        if not teclas_objetivo:
            return False
        self._teclas_objetivo = teclas_objetivo
        self._teclas_presionadas = set()
        try:
            self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.start()
            return True
        except Exception:
            self._listener = None
            return False

    def _canon(self, key):
        try:
            return self._listener.canonical(key)
        except Exception:
            return key

    def _on_press(self, key):
        self._teclas_presionadas.add(self._canon(key))
        if self._teclas_objetivo and self._teclas_objetivo <= self._teclas_presionadas:
            self.activado.emit()

    def _on_release(self, key):
        self._teclas_presionadas.discard(self._canon(key))

    def detener(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._teclas_presionadas = set()
