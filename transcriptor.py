import json
import os
import sys
import tempfile
import threading
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

PUERTO = int(os.environ.get("TRANSCRIPTOR_PUERTO", "8411"))
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODELO_RESUMEN = os.environ.get("TRANSCRIPTOR_MODELO_RESUMEN", "qwen3:14b")
MODELOS_WHISPER = {"rapido": "small", "preciso": "large-v3-turbo"}
MAX_BYTES = 2 * 1024**3
HTML = Path(__file__).with_name("index.html")

trabajos: dict[str, dict] = {}
modelos: dict[tuple[str, str], object] = {}
cerrojo_modelo = threading.Lock()
# La GPU se descarta en cuanto falla una vez: CUDA puede cargar el modelo y
# luego no encontrar cuBLAS o cuDNN al transcribir.
gpu = {"usable": True}


def cargar_modelo(calidad: str, dispositivo: str):
    from faster_whisper import WhisperModel

    clave = (MODELOS_WHISPER[calidad], dispositivo)
    with cerrojo_modelo:
        if clave not in modelos:
            tipo = "float16" if dispositivo == "cuda" else "int8"
            modelos[clave] = WhisperModel(clave[0], device=dispositivo, compute_type=tipo)
        return modelos[clave]


def pasar_audio(t: dict, ruta: Path, calidad: str, idioma: str | None, dispositivo: str):
    t["estado"] = "cargando el modelo (la primera vez se descarga)"
    modelo = cargar_modelo(calidad, dispositivo)
    t["estado"] = "transcribiendo" + (" con la GPU" if dispositivo == "cuda" else "")
    t["segmentos"], t["progreso"] = [], 0
    segmentos, info = modelo.transcribe(str(ruta), language=idioma, vad_filter=True)
    t["idioma"] = info.language
    t["duracion"] = info.duration
    for s in segmentos:
        t["segmentos"].append({"ini": s.start, "fin": s.end, "texto": s.text.strip()})
        t["progreso"] = min(1.0, s.end / info.duration) if info.duration else 0


def transcribir(id_: str, ruta: Path, calidad: str, idioma: str | None):
    t = trabajos[id_]
    try:
        if gpu["usable"]:
            try:
                pasar_audio(t, ruta, calidad, idioma, "cuda")
            except Exception:
                # Sin GPU NVIDIA o sin sus librerías: en CPU va más lento, pero va.
                gpu["usable"] = False
        if not gpu["usable"]:
            pasar_audio(t, ruta, calidad, idioma, "cpu")
        t["progreso"] = 1.0
        t["estado"] = "listo"
    except Exception as e:
        t["estado"] = "error"
        t["error"] = f"No se pudo transcribir: {e}"
    finally:
        ruta.unlink(missing_ok=True)


def resumir(texto: str) -> str:
    prompt = (
        "Resume esta transcripción en español. Devuelve tres apartados con estos títulos exactos:\n"
        "RESUMEN: tres o cuatro frases.\nPUNTOS CLAVE: lista con guiones.\n"
        "TAREAS: lista con guiones de lo que alguien se comprometió a hacer, con quién y cuándo si se dice; "
        "si no hay ninguna, escribe 'Ninguna'.\nTexto plano, sin negritas ni markdown. "
        "No inventes nada que no esté en el texto.\n\n"
        f"TRANSCRIPCIÓN:\n{texto[:60000]}"
    )
    cuerpo = json.dumps({
        "model": MODELO_RESUMEN,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_ctx": 32768, "temperature": 0.2},
    }).encode()
    pet = urllib.request.Request(f"{OLLAMA}/api/chat", data=cuerpo, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pet, timeout=600) as r:
        return json.load(r)["message"]["content"].replace("**", "").strip()


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def responder(self, codigo: int, datos, tipo="application/json"):
        cuerpo = datos if isinstance(datos, bytes) else json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/":
            return self.responder(200, HTML.read_bytes(), "text/html")
        if self.path.startswith("/estado/"):
            t = trabajos.get(self.path.removeprefix("/estado/"))
            return self.responder(200, t) if t else self.responder(404, {"error": "No existe"})
        self.responder(404, {"error": "No existe"})

    def do_POST(self):
        # Solo desde la propia página: otra web abierta en el navegador no puede mandar trabajos.
        if self.headers.get("Origin") not in (None, f"http://127.0.0.1:{PUERTO}", f"http://localhost:{PUERTO}"):
            return self.responder(403, {"error": "Origen no permitido"})
        if self.path == "/transcribir":
            return self.nuevo_trabajo()
        if self.path == "/resumir":
            return self.resumen()
        self.responder(404, {"error": "No existe"})

    def nuevo_trabajo(self):
        tam = int(self.headers.get("Content-Length") or 0)
        if not 0 < tam <= MAX_BYTES:
            return self.responder(400, {"error": "El archivo está vacío o pasa de 2 GB."})
        calidad = self.headers.get("X-Calidad", "rapido")
        if calidad not in MODELOS_WHISPER:
            calidad = "rapido"
        idioma = self.headers.get("X-Idioma") or None
        if idioma and (len(idioma) > 3 or not idioma.isalpha()):
            idioma = None
        sufijo = Path(unquote(self.headers.get("X-Nombre", "audio"))).suffix[:8]
        fd, nombre = tempfile.mkstemp(suffix=sufijo, prefix="transcriptor-")
        with os.fdopen(fd, "wb") as f:
            restante = tam
            while restante:
                trozo = self.rfile.read(min(1 << 20, restante))
                if not trozo:
                    break
                f.write(trozo)
                restante -= len(trozo)
        id_ = uuid.uuid4().hex
        trabajos[id_] = {"estado": "en cola", "progreso": 0, "segmentos": [], "idioma": None, "duracion": None}
        threading.Thread(target=transcribir, args=(id_, Path(nombre), calidad, idioma), daemon=True).start()
        self.responder(200, {"id": id_})

    def resumen(self):
        tam = int(self.headers.get("Content-Length") or 0)
        try:
            texto = json.loads(self.rfile.read(min(tam, 5_000_000)) or b"{}").get("texto", "")
        except json.JSONDecodeError:
            texto = ""
        if not texto.strip():
            return self.responder(400, {"error": "No hay texto que resumir."})
        try:
            self.responder(200, {"resumen": resumir(texto)})
        except Exception as e:
            self.responder(502, {"error": f"No se pudo hablar con Ollama ({OLLAMA}). ¿Está abierto y tiene {MODELO_RESUMEN}? Detalle: {e}"})


def main():
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    url = f"http://127.0.0.1:{PUERTO}"
    print(f"Transcriptor en {url}  (Ctrl+C para cerrar)")
    if "--sin-navegador" not in sys.argv:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
