@echo off
REM Compila Battery Widget como un .exe independiente en Windows.
REM Requiere tener Python 3.10+ instalado (con "Add python.exe to PATH" marcado
REM al instalarlo desde python.org).

cd /d "%~dp0"

if not exist ".venv-windows" (
    echo Creando entorno virtual...
    python -m venv .venv-windows
    call .venv-windows\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements-windows.txt
) else (
    call .venv-windows\Scripts\activate.bat
)

echo.
echo Compilando el ejecutable...
REM app.upower/dbus son exclusivos de Linux; no se usan nunca en Windows
REM (ver app/widget.py), asi que se excluyen para que no fallen al compilar.
pyinstaller --noconfirm --onefile --windowed --name BatteryWidget --icon assets\icon.ico ^
    --exclude-module app.upower --exclude-module dbus main.py

echo.
if exist "dist\BatteryWidget.exe" (
    echo Listo: dist\BatteryWidget.exe
    echo Puedes copiar ese archivo a cualquier carpeta o crear un acceso directo.
) else (
    echo Algo fallo. Revisa los mensajes de arriba.
)
pause
