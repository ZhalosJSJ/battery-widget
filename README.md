# Battery Widget

Widget de escritorio para Linux que muestra en tiempo real el nivel de batería
de tu computador y de los dispositivos conectados (audífonos Bluetooth,
mouse/teclado inalámbricos, etc.), usando el servicio del sistema **UPower**
(el mismo que usa GNOME/KDE para mostrar la batería). Queda funcionando en
segundo plano en la bandeja del sistema y avisa con notificaciones cuando un
dispositivo cruza los porcentajes que definas (por defecto 50%, 25% y 10%).

## Requisitos

- Linux con `upower` corriendo (viene instalado por defecto en la mayoría de
  distribuciones con GNOME/KDE/XFCE).
- `python3-dbus` a nivel de sistema (normalmente ya viene instalado; si no,
  `sudo apt install python3-dbus`).
- Python 3.9+.

## Uso

```bash
./run.sh
```

La primera vez crea un entorno virtual (`.venv`, con acceso a los paquetes
del sistema para reutilizar `dbus-python`) e instala PySide6. Las siguientes
veces solo abre la app.

- Por defecto arranca en **modo mini**, pegado al extremo izquierdo de la
  pantalla: solo se ve una mini batería del dispositivo elegido (o el de
  menor porcentaje) más un botón **⤢** para pasar a tamaño completo cuando
  haga falta. El widget aparece flotando sobre las demás ventanas; se puede
  arrastrar desde cualquier punto y recuerda su posición.
- En tamaño completo, el botón **▭** vuelve a mini; clic derecho sobre la
  mini batería para elegir qué dispositivo mostrar ahí (o dejarla en
  "Automático").
- **⌨ Atajo de teclado global**: en Configuración se puede grabar una
  combinación (por defecto `Ctrl+Alt+B`) que alterna entre mini y tamaño
  completo desde cualquier parte del sistema, aunque la app no tenga el
  foco — no hace falta hacer clic en el ícono de la bandeja primero. Se
  puede desactivar con el checkbox si no se usa. Usa la librería `pynput`,
  que en Linux necesita una sesión X11 (puede no andar en Wayland puro) y
  para eso escucha eventos de teclado a nivel de todo el sistema — solo
  reacciona a la combinación configurada, no guarda ni transmite nada.
- El botón **⚙** abre la configuración: umbrales de aviso, intervalo de
  actualización, inicio automático con la sesión y qué dispositivos mostrar
  u ocultar. En modo mini también se puede abrir desde el menú de la
  bandeja del sistema (clic derecho → "Configuración…").
- El botón **—** oculta el widget sin cerrar la app (sigue actualizando y
  avisando en segundo plano); para volver a mostrarlo, clic izquierdo en el
  ícono de la bandeja del sistema.
- "Salir" en el menú de la bandeja (clic derecho) cierra la aplicación.
- El botón **🔄** fuerza un refresco inmediato (útil justo después de conectar algo).
- Desde **⚙ Configuración** también se puede: activar **🔕 No molestar**
  (pausa los avisos de umbral por 1h/4h/8h o indefinido, sin dejar de leer la
  batería), y abrir **📈 Ver historial de batería** (gráfico simple del %
  de cada dispositivo en las últimas horas/días, guardado en
  `~/.config/battery_widget/historial.db`).
- La primera vez que aparece un dispositivo nunca antes visto (recién
  emparejado o conectado), llega una notificación avisándolo.
- Activando **🌐 Mostrar test de conectividad** en Configuración aparece un
  mini panel bajo la batería con un botón **Probar**: mide la latencia
  (ping) a un par de servidores públicos y la muestra con barras de señal
  estilo videojuego (Excelente/Buena/Regular/Mala/Sin conexión), y debajo la
  velocidad de bajada (celeste) y de subida (morado) en Mbps — medidas
  transfiriendo un archivo de prueba contra `speed.cloudflare.com` (sin
  cuenta ni API key). Es una medición aproximada de una sola conexión, no un
  test de laboratorio con múltiples streams. No corre solo ni consume red en
  segundo plano — solo al apretar el botón.

## Cómo se leen los dispositivos

Se usa `org.freedesktop.UPower` vía D-Bus, la misma fuente que el comando
`upower -e` / `upower -i`. Cualquier dispositivo que UPower detecte con
batería aparece automáticamente: batería del computador, audífonos y otros
periféricos Bluetooth con perfil de batería, mouse/teclado inalámbricos, etc.

Además, si tienes un celular **Android** conectado por USB-C con depuración
USB activada, la app lo detecta automáticamente vía `adb`
(`adb shell dumpsys battery`) y lo muestra junto a los demás dispositivos.

Para activarlo:

1. Instala la herramienta `adb`:
   ```bash
   sudo apt-get install -y android-tools-adb
   ```
2. En el celular: **Ajustes → Acerca del teléfono** → toca 7 veces
   "Número de compilación" para activar "Opciones de desarrollador".
3. **Ajustes → Opciones de desarrollador** → activa **Depuración USB**.
4. Conecta el celular por USB-C. La primera vez aparece un diálogo en el
   celular pidiendo autorizar este computador ("¿Permitir depuración USB?") —
   acéptalo (puedes marcar "Recordar siempre" para no repetirlo).
5. El celular debería aparecer solo en el widget en el siguiente ciclo de
   actualización (según el intervalo configurado).

Se puede desactivar esta búsqueda desde **⚙ Configuración** si no se usa o
si se prefiere no tener `adb` corriendo en segundo plano.

(iPhone no está soportado por ahora — requeriría `libimobiledevice`; avísame
si lo necesitas.)

## Umbrales personalizados por dispositivo

En **⚙ Configuración → "Umbrales personalizados por dispositivo"** se puede
marcar "Personalizar" en un dispositivo puntual y darle sus propios
porcentajes de aviso (ej. avisar el celular a 60/30/15% pero dejar los
audífonos con los umbrales globales de 50/25/10%). Un dispositivo sin
personalizar siempre usa los umbrales globales de arriba.

## Windows

La versión Windows solo lee la **batería del propio computador** (vía
`psutil`) — Bluetooth/UPower no tiene equivalente simple en Windows, así que
por ahora los audífonos u otros periféricos no aparecen ahí. El resto de las
funciones (historial, modo mini, no molestar, umbrales por dispositivo,
Android por `adb`) funciona igual que en Linux.

Para compilarlo en tu PC Windows:

1. Instala [Python 3.10+](https://www.python.org/downloads/) marcando **"Add
   python.exe to PATH"** durante la instalación.
2. Copia esta carpeta completa (`battery_widget`) a tu PC Windows.
3. Haz doble clic en **`build_windows.bat`**. La primera vez crea un entorno
   virtual e instala las dependencias (PySide6, psutil, PyInstaller); después
   compila el ejecutable.
4. El resultado queda en `dist\BatteryWidget.exe` — es un archivo único,
   independiente, se puede copiar a cualquier carpeta o crear un acceso
   directo hacia él.
5. Para que inicie con Windows: marca "Iniciar automáticamente al iniciar
   sesión" en **⚙ Configuración** (deja un `.bat` en la carpeta de inicio de
   Windows apuntando al `.exe`).

Esta parte **no la pude probar yo** (no tengo una máquina Windows disponible)
— avísame qué falla al compilarlo o correrlo y lo ajustamos desde ahí.

Si además quieres usar el celular Android por USB en Windows, instala
[Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)
y agrega esa carpeta al `PATH` de Windows (para tener `adb.exe` disponible);
el resto funciona igual que en Linux.

## Estructura

```
main.py                    punto de entrada
app/upower.py               lectura de dispositivos vía D-Bus/UPower (Linux)
app/battery_pc.py            lectura de la batería del PC vía psutil (Windows/otros)
app/config.py                config en ~/.config/battery_widget/config.json
app/widget.py                ventana flotante sin bordes
app/tray.py                  ícono de bandeja + lógica de notificaciones por umbral
app/settings_dialog.py       diálogo de configuración
app/adb_battery.py            lectura de batería Android por adb
app/historial.py              guarda lecturas en SQLite para el historial
app/historial_dialog.py       diálogo con el gráfico de historial
app/red.py                    test de conectividad/latencia bajo demanda (ping)
build_windows.bat            compila el .exe de Windows (correr en Windows)
requirements-windows.txt     dependencias para la build de Windows
```

La configuración (umbrales, posición de la ventana, dispositivos ocultos,
etc.) se guarda en `~/.config/battery_widget/config.json`.
