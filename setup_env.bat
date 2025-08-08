@echo off
REM Crear entorno virtual
python -m venv venv

REM Activar entorno virtual
call venv\Scripts\activate.bat

REM Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Entorno virtual configurado y dependencias instaladas.
echo Para activar el entorno en el futuro, ejecuta:
echo     call venv\Scripts\activate.bat
pause