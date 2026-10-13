@echo off
cd /d "%~dp0"
if not exist .venv (echo Primero ejecuta instalar.bat & pause & exit /b 1)
.venv\Scripts\python transcriptor.py
