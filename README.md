# Transcriptor · SIMBAI Lab

Arrastras un audio o un vídeo y te devuelve el texto, los subtítulos y un resumen con las tareas. Todo pasa en tu ordenador: nada se sube a internet.

- **Transcripción** con [faster-whisper](https://github.com/SYSTRAN/faster-whisper): modelo `small` (rápido) o `large-v3-turbo` (preciso). Usa la GPU NVIDIA si tiene sus librerías; si no, la CPU.
- **Resumen** con [Ollama](https://ollama.com) en local: resumen, puntos clave y tareas.
- **Descargas** en `.txt` y subtítulos `.srt`.
- Detecta el idioma solo o se lo indicas (español, inglés, alemán, francés, italiano, portugués).

## Instalar (Windows)

1. Python 3.11 o superior.
2. Doble clic en `instalar.bat`.
3. Para los resúmenes: instala Ollama y ejecuta `ollama pull qwen3:14b`.

## Usar

Doble clic en `iniciar.bat`: se abre en el navegador en `http://127.0.0.1:8411`. La primera transcripción descarga el modelo de Whisper (unos 500 MB el rápido, 1,6 GB el preciso).

## Configuración

Variables de entorno, todas opcionales:

| Variable | Por defecto |
|---|---|
| `TRANSCRIPTOR_PUERTO` | `8411` |
| `OLLAMA_URL` | `http://localhost:11434` |
| `TRANSCRIPTOR_MODELO_RESUMEN` | `qwen3:14b` |

## Linux y macOS

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python transcriptor.py
```
