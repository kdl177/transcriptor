@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Transcriptor de SIMBAI: instalacion
where python >nul 2>nul || (echo Falta Python 3.11 o superior: https://www.python.org/downloads/ ^(marca "Add python.exe to PATH"^) & pause & exit /b 1)
if not exist .venv python -m venv .venv || (echo No se pudo crear el entorno. & pause & exit /b 1)
.venv\Scripts\python -m pip install --upgrade pip -q
.venv\Scripts\python -m pip install -r requirements.txt -q || (echo Fallo al instalar las dependencias. & pause & exit /b 1)
echo.
echo Listo. Abre el transcriptor con iniciar.bat
echo Para los resumenes instala Ollama ^(https://ollama.com^) y ejecuta: ollama pull qwen3:14b
pause
