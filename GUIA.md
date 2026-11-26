# Guía rápida — Battery Widget

Referencia de comandos y datos importantes de la app, pensada para tenerla a
mano al migrar a otro computador (ej. tu PC con Windows 11).

## 1. Comandos esenciales

### Linux (este computador)

```bash
cd ~/Descargas/battery_widget
./run.sh                          # primera vez: crea .venv e instala todo; luego solo abre la app
```

```bash
pkill -f "python.*main.py"        # cerrar la app a la fuerza (si quedó colgada)
```

```bash
sudo apt-get install -y android-tools-adb   # para leer el celular Android por USB
adb devices                                  # ver si el celular está autorizado
```

```bash
upower -e                         # listar dispositivos que ve UPower (batería PC, Bluetooth)
upower -i /org/freedesktop/UPower/devices/battery_BAT0   # detalle de la batería del PC
bluetoothctl info <MAC>           # ver si un dispositivo Bluetooth está conectado
```

### Windows 11 (PC nuevo)

```bat
REM 1. Instalar Python 3.10+ desde python.org, marcando "Add python.exe to PATH"
REM 2. Copiar toda la carpeta battery_widget al PC Windows
REM 3. Doble clic en:
build_windows.bat
REM Genera dist\BatteryWidget.exe (independiente, se puede mover a cualquier carpeta)
```

Para tener `adb` (celular Android) en Windows: instalar
[Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)
y agregar esa carpeta al PATH de Windows.

## 2. Ubicaciones importantes

| Qué | Linux | Windows |
|---|---|---|
| Configuración | `~/.config/battery_widget/config.json` | `%USERPROFILE%\.config\battery_widget\config.json` |
| Historial de batería (SQLite) | `~/.config/battery_widget/historial.db` | `%USERPROFILE%\.config\battery_widget\historial.db` |
| Autoarranque | `~/.config/autostart/battery-widget.desktop` | `.bat` en la carpeta *Startup* (`shell:startup`) |
| Acceso directo / menú | `~/.local/share/applications/battery-widget.desktop` | crear acceso directo a `dist\BatteryWidget.exe` a mano |
| Ejecutable compilado | — (se corre con `run.sh`) | `dist\BatteryWidget.exe` (tras correr `build_windows.bat`) |

Todo esto se genera solo la primera vez que corre la app — **no hace falta
copiar estos archivos entre computadores**, cada uno arranca con su propia
configuración por defecto.

## 3. Qué SÍ copiar al migrar a Windows y qué NO

**Copiar** (es el código de la app):
```
app/
assets/
main.py
requirements.txt
requirements-windows.txt
build_windows.bat
run.sh
README.md
GUIA.md
```

**No copiar** (son específicos de este computador / se regeneran solos):
```
.venv/                 → entorno virtual de Linux, no sirve en Windows
__pycache__/
~/.config/battery_widget/config.json    → tiene tus dispositivos Bluetooth de ESTE PC
~/.config/battery_widget/historial.db   → historial de batería de ESTE PC
```

## 4. Diferencias importantes en Windows

- Solo se lee la **batería del propio computador** (vía `psutil`). Windows no
  tiene un equivalente simple a UPower, así que **audífonos/Bluetooth no
  aparecen** ahí (si más adelante quieres intentarlo, se puede evaluar, pero
  no es trivial ni 100% confiable).
- El celular Android por USB (`adb`) sí funciona igual, si instalas
  Android Platform Tools.
- El atajo de teclado global (`Ctrl+Alt+B` por defecto) usa `pynput`, que en
  Windows debería funcionar nativo — **esto no lo pude probar yo** porque no
  tengo una máquina Windows; avísame si falla al presionarlo.
- El modo mini, No molestar, umbrales por dispositivo, historial gráfico y
  test de conectividad (ping + velocidad) funcionan igual en ambos sistemas.

## 5. Funciones de la app (resumen)

- **Modo mini** (por defecto, extremo izquierdo de la pantalla): mini batería
  del dispositivo con menor carga + botón **⤢** para expandir.
- **Atajo global `Ctrl+Alt+B`**: alterna mini/completo desde cualquier parte
  del sistema (configurable en ⚙ Configuración).
- **⚙ Configuración**: umbrales de aviso (globales y por dispositivo),
  intervalo de actualización, autoarranque, activar/desactivar ADB, modo
  mini (qué dispositivo priorizar), 🔕 No molestar (con duración), 📈 ver
  historial, 🌐 activar test de conectividad, atajo de teclado.
- **🌐 Test de conectividad** (opcional, bajo demanda): ping + velocidad de
  bajada/subida contra `speed.cloudflare.com`, con barras estilo videojuego.
- Notificaciones nativas por D-Bus en Linux (`org.freedesktop.Notifications`);
  en Windows caen solas por `QSystemTrayIcon.showMessage()`.

## 6. Problemas ya vistos y cómo se resolvieron (por si se repiten)

- **"No se ha podido localizar el paquete"** al instalar con `apt`: revisar
  que no se haya colado un carácter de más al copiar el comando (typo con `~`
  visto en esta sesión), y correr `sudo apt-get update` primero.
- **`libxcb-cursor0` faltante**: `sudo apt-get install -y libxcb-cursor0`
  (Qt 6.5+ lo necesita para el plugin de pantalla `xcb`).
- **Notificaciones que no aparecen en XFCE**: `QSystemTrayIcon.showMessage()`
  no siempre funciona ahí — la app ya usa D-Bus directo como solución
  (`org.freedesktop.Notifications`), igual que `notify-send`.
- **Audífonos Bluetooth que dejan de mostrar batería**: pasa cuando el
  dispositivo está conectado pero no envió el dato de batería a BlueZ en esa
  sesión (depende del firmware del audífono, no es bug de la app). Se
  arregla desconectando y reconectando el dispositivo Bluetooth.
- **Celular Android en "unauthorized"**: hay que aceptar el diálogo "¿Permitir
  depuración USB?" en la pantalla del celular; si no aparece, probar
  `adb kill-server && adb start-server` y reconectar el cable.
- **El widget no cambiaba de tamaño hasta apretar el botón dos veces**: era
  un problema de timing de Qt (el layout se recalcula un ciclo después de
  ocultar/mostrar contenido); ya está corregido.
