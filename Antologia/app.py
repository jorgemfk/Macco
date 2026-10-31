import os
import json
import re
import time
import threading
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
from flask import Flask, render_template, jsonify
from flask_sock import Sock
from openai import OpenAI

# ============================================================
# CONFIGURACIÓN
# ============================================================

LOG_DIR = Path(os.getenv("MACCO_LOG_DIR", "/home/jorge/logMacco"))
#LOG_DIR = Path(os.getenv("MACCO_LOG_DIR", "/Users/jorgeluis/logMacco"))

HOST = os.getenv("MACCO_HOST", "0.0.0.0")
PORT = int(os.getenv("MACCO_PORT", "8080"))

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

# Segundos que dura el visual central antes de la frase de despedida.
VISUAL_SECONDS = float(os.getenv("MACCO_VISUAL_SECONDS", "25"))
# Segundos que permanece la frase de despedida.
PHRASE_SECONDS = float(os.getenv("MACCO_PHRASE_SECONDS", "12"))
# Pausa (pantalla apagándose) antes de redibujar con el siguiente día.
INTERLUDE_SECONDS = float(os.getenv("MACCO_INTERLUDE_SECONDS", "4"))

# Micrófono conectado a la Raspberry (sonido ambiental -> expansión del visual).
AUDIO_ENABLED = os.getenv("MACCO_AUDIO", "1") != "0"
AUDIO_DEVICE = os.getenv("MACCO_AUDIO_DEVICE")      # índice o nombre; vacío = predeterminado
AUDIO_FPS = 25                                      # mensajes de nivel por segundo

app = Flask(__name__)
sock = Sock(app)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=40.0, max_retries=1)
executor = ThreadPoolExecutor(max_workers=2)

clients = set()
clients_lock = threading.Lock()

state_lock = threading.Lock()
state = {
    "mode": "idle",        # idle | visual | phrase | interlude
    "day": None,           # último payload "day"
    "phrase": None,        # último payload "phrase" (solo mientras se muestra)
    "cycle": 0,
    "connected_clients": 0,
}

# Emociones de visión (las que se leen del log).
LOG_EMOTIONS = ["Enojo", "Asco", "Miedo", "Felicidad", "Tristeza", "Sorpresa", "Neutral"]

# Sentimientos permitidos para la frase de despedida.
EMOTIONS = [
    "Tristeza", "Nostalgia", "Miedo", "Deseo", "Ansiedad", "Curiosidad",
    "Fascinación", "Rechazo", "Ternura", "Vergüenza", "Soledad", "Alivio",
    "Inquietud", "Asombro", "Calma", "Esperanza",
]


def norm(s):
    """Minúsculas y sin acentos: 'Oído' -> 'oido'."""
    s = unicodedata.normalize("NFD", str(s))
    return s.encode("ascii", "ignore").decode().lower().strip()


EMO_CANON = {norm(e): e for e in LOG_EMOTIONS}

# ============================================================
# LECTURA DE LOGS
# ============================================================

def parse_log_date(path: Path):
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.log", path.name)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def list_log_days():
    """Días con archivo de log, del más antiguo al más reciente."""
    if not LOG_DIR.exists():
        return []
    days = set()
    for path in LOG_DIR.glob("*.log"):
        d = parse_log_date(path)
        if d is not None and d <= date.today():
            days.add(d)
    return sorted(days)


def add_emotions(obj, counter):
    """Acepta {"Enojo":1,"Asco":2}, ["Enojo","Miedo"] o combinaciones."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            canon = EMO_CANON.get(norm(k))
            if canon is not None:
                try:
                    n = int(round(float(v)))
                except (TypeError, ValueError):
                    n = 1
                if n > 0:
                    counter[canon] += n
            elif isinstance(v, (dict, list)):
                add_emotions(v, counter)
    elif isinstance(obj, list):
        for el in obj:
            add_emotions(el, counter)
    elif isinstance(obj, str):
        canon = EMO_CANON.get(norm(obj))
        if canon:
            counter[canon] += 1


def parse_loc(obj):
    """{"x":20,"y":50} (porcentaje) -> [20.0, 50.0] o None."""
    try:
        if isinstance(obj, dict):
            x, y = float(obj["x"]), float(obj["y"])
        elif isinstance(obj, (list, tuple)) and len(obj) >= 2:
            x, y = float(obj[0]), float(obj[1])
        else:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return [round(min(100.0, max(0.0, x)), 1), round(min(100.0, max(0.0, y)), 1)]


def read_day(day: date):
    """Lee el log de un día y devuelve todo lo que necesitan las 4 secciones."""
    path = LOG_DIR / f"{day.isoformat()}.log"

    entries = 0
    counts = Counter()
    words, seen = [], set()
    emo = Counter()
    emo_records = 0
    locs = []
    thoughts = []

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict):
                    continue

                entries += 1
                sentido = norm(item.get("sentido", ""))
                counts[sentido] += 1

                if sentido == "oido":
                    text = str(item.get("texto_original", "")).strip()
                    key = text.lower()
                    if text and key not in seen:
                        seen.add(key)
                        words.append(text[:40])

                elif sentido == "vista":
                    before = sum(emo.values())
                    add_emotions(item.get("emociones_recientes"), emo)
                    if sum(emo.values()) > before:
                        emo_records += 1
                    loc = parse_loc(item.get("localizacion"))
                    if loc:
                        locs.append(loc)

                elif sentido == "pensamiento":
                    t = str(item.get("pensamiento", "")).strip()
                    if t:
                        thoughts.append({
                            "fecha": item.get("fecha", day.isoformat()),
                            "pensamiento": t,
                        })
    except OSError as exc:
        print(f"[LOG] No se pudo leer {path}: {exc}")

    # Máximo 60 puntos de localización, conservando el orden cronológico.
    if len(locs) > 60:
        step = len(locs) / 60
        locs = [locs[int(i * step)] for i in range(60)]

    total = sum(emo.values())
    emotions = [
        {
            "name": name,
            "count": emo[name],
            "pct": round(100 * emo[name] / total) if total else 0,
        }
        for name in LOG_EMOTIONS
    ]

    return {
        "day": day.isoformat(),
        "file": path.name,
        "entries": entries,
        "counts": {
            "pensamiento": counts["pensamiento"],
            "oido": counts["oido"],
            "vista": counts["vista"],
            "tacto": counts["tacto"],
            "olfato": counts["olfato"],
            "emociones": emo_records,
        },
        "words": words,
        "emotions": emotions,
        "locations": locs,          # vacío -> el navegador la inventa
        "visual_seconds": VISUAL_SECONDS,
        "_thoughts": thoughts,      # no se envía al navegador
    }


# ============================================================
# OPENAI — FRASE DE DESPEDIDA
# ============================================================

SYSTEM_PROMPT = """
Eres la voz antológica de MACCO, una instalación artística que ha
acumulado pensamientos durante meses.

Recibes los pensamientos que MACCO produjo durante UN DÍA concreto.
Ese día termina y MACCO se despide de él.

Tu tarea NO es resumirlos literalmente.
Transfórmalos en una frase breve de despedida, como si naciera de la
memoria de ese día.

La frase debe ser:
- íntima
- intensa
- extraña
- emocional
- concreta
- ligeramente ambigua
- diferente de las frases anteriores
- inesperada
- en tono de despedida

No digas que eres una IA.
No menciones sensores, datos, archivos, modelos, programación ni JSON.
No describas el proceso de generación.
No uses fórmulas como:
"algo cambió dentro de mí",
"algo permanece",
"todavía recuerdo",
"no sé qué siento",
"cada persona deja una huella".

Evita comenzar repetidamente con "Hoy", "Recuerdo", "A veces" o "No sé".
No conviertas la frase en una explicación.

Puede haber contradicción:
deseo y rechazo, memoria y olvido, curiosidad y miedo,
cercanía y abandono.

El sentimiento debe ser una sola palabra de la lista permitida.

Responde ÚNICAMENTE con JSON válido:

{
  "frase": "...",
  "sentimiento": "..."
}

El campo sentimiento debe ser exactamente una de estas opciones:
Tristeza, Nostalgia, Miedo, Deseo, Ansiedad, Curiosidad,
Fascinación, Rechazo, Ternura, Vergüenza, Soledad, Alivio,
Inquietud, Asombro, Calma, Esperanza.

Máximo 35 palabras para la frase. y entre parentesis en ingles ejemplo:
Adios, me siento solo. (goodbye, I feel alone.)
"""


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def day_material(thoughts, data):
    """
    Materia prima de la frase. Si hay pensamientos, se usan. Si el día no
    tiene (logs antiguos), se usa lo demás que quedó registrado: palabras
    oídas, emociones dominantes y cantidad de actividad.
    """
    if thoughts:
        return "Pensamientos originales de ese día:\n" + "\n".join(
            f"- {t['pensamiento']}" for t in thoughts[-80:])

    lines = []
    if data["words"]:
        lines.append("Palabras que se oyeron: " + ", ".join(data["words"][:40]))
    top = sorted((e for e in data["emotions"] if e["count"]),
                 key=lambda e: e["count"], reverse=True)[:4]
    if top:
        lines.append("Emociones que más atravesaron ese día: " +
                     ", ".join(f"{e['name']} ({e['pct']}%)" for e in top))
    if data["entries"]:
        lines.append(f"Fue un día con {data['entries']} registros de actividad.")
    if not lines:
        lines.append("Un día casi sin huellas: silencio, nadie a quien recordar.")
    return ("Ese día no dejó pensamientos escritos, solo estos restos:\n"
            + "\n".join(f"- {l}" for l in lines))


def generate_farewell(thoughts, day, previous=None, data=None):
    source = day_material(thoughts, data)

    previous_text = ""
    if previous:
        previous_text = f"""
Frase de despedida inmediatamente anterior:
"{previous['frase']}"

No la reformules ni repitas su idea.
"""

    user_prompt = f"""
Fecha de la memoria: {day.isoformat()}

{source}

{previous_text}

Crea una nueva frase de despedida para ese día.
No la copies. No la resumas.
"""

    kwargs = {}
    # Los modelos de razonamiento gastan tokens "pensando": hay que darles
    # margen y pedir razonamiento mínimo, o la respuesta sale vacía.
    if OPENAI_MODEL.startswith(("gpt-5", "o")):
        kwargs["reasoning"] = {"effort": "minimal"}

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
            max_output_tokens=800,
            **kwargs,
        )
        data = extract_json(response.output_text)

        frase = str(data.get("frase", "")).strip()
        sentimiento = str(data.get("sentimiento", "")).strip()
        if not frase:
            raise ValueError("OpenAI devolvió una frase vacía")
        if sentimiento not in EMOTIONS:
            sentimiento = "Neutral"

        return {
            "frase": frase,
            "sentimiento": sentimiento,
            "fecha": day.isoformat(),
            "modelo": OPENAI_MODEL,
        }

    except Exception as exc:
        print(f"[OPENAI] Error: {type(exc).__name__}: {exc}")
        if not thoughts:
            return None        # sin pensamientos y sin API: no se muestra frase
        return {
            "frase": thoughts[-1]["pensamiento"],
            "sentimiento": "Neutral",
            "fecha": day.isoformat(),
            "modelo": "fallback",
        }


# ============================================================
# WEBSOCKET
# ============================================================

def broadcast(payload):
    message = json.dumps(payload, ensure_ascii=False)
    dead = []

    with clients_lock:
        for ws in list(clients):
            try:
                ws.send(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            clients.discard(ws)
        with state_lock:
            state["connected_clients"] = len(clients)


@sock.route("/ws")
def websocket(ws):
    with clients_lock:
        clients.add(ws)
        with state_lock:
            state["connected_clients"] = len(clients)

    print("[WS] cliente conectado")

    # Un navegador que se conecta a mitad de un día recibe lo que se muestra.
    try:
        with state_lock:
            day, phrase, mode = state["day"], state["phrase"], state["mode"]
        if day and mode in ("visual", "phrase"):
            ws.send(json.dumps(day, ensure_ascii=False))
        if phrase and mode == "phrase":
            ws.send(json.dumps(phrase, ensure_ascii=False))
    except Exception:
        pass

    try:
        while True:
            message = ws.receive()
            if message is None:
                break
            if message == "ping":
                ws.send("pong")
    except Exception as exc:
        print(f"[WS] conexión terminada: {exc}")
    finally:
        with clients_lock:
            clients.discard(ws)
            with state_lock:
                state["connected_clients"] = len(clients)
        print("[WS] cliente desconectado")


# ============================================================
# MICRÓFONO (en la Raspberry)
# ============================================================

audio_lock = threading.Lock()
audio_rms = 0.0


def audio_callback(indata, frames, time_info, status):
    global audio_rms
    rms = float(np.sqrt(np.mean(np.square(indata[:, 0]))))
    with audio_lock:
        audio_rms = rms


def audio_loop():
    """
    Lee el micrófono, normaliza con auto-ganancia (aprende el ruido de
    fondo y el pico reciente) y envía el nivel 0..1 a los navegadores.
    """
    try:
        import numpy as _np  # noqa: F401
        import sounddevice as sd
    except ImportError as exc:
        print(f"[AUDIO] Desactivado, falta una librería: {exc}")
        return

    device = AUDIO_DEVICE
    if device is not None and device.strip().lstrip("-").isdigit():
        device = int(device)

    floor, peak = 0.004, 0.03
    smooth = 0.0

    try:
        stream = sd.InputStream(
            device=device or None, channels=1, samplerate=16000,
            blocksize=512, callback=audio_callback,
        )
    except Exception as exc:
        print(f"[AUDIO] No se pudo abrir el micrófono: {exc}")
        return

    with stream:
        print(f"[AUDIO] Micrófono activo: {sd.query_devices(stream.device)['name']}")
        period = 1.0 / AUDIO_FPS
        while True:
            time.sleep(period)
            with audio_lock:
                rms = audio_rms

            floor = rms if rms < floor else floor + (rms - floor) * 0.002
            peak = rms if rms > peak else peak + (floor + 0.02 - peak) * 0.004
            level = min(1.0, max(0.0, (rms - floor) / (peak - floor + 1e-4)))
            smooth += (level - smooth) * 0.5

            with clients_lock:
                has_clients = bool(clients)
            if has_clients:
                broadcast({"type": "audio", "level": round(smooth, 3)})


# ============================================================
# WEB
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    with state_lock:
        result = {
            "mode": state["mode"],
            "cycle": state["cycle"],
            "connected_clients": state["connected_clients"],
            "day": state["day"]["day"] if state["day"] else None,
        }
    result["today"] = date.today().isoformat()
    return jsonify(result)


@app.route("/api/scan")
def api_scan():
    days = list_log_days()
    return jsonify({
        "log_dir": str(LOG_DIR),
        "today": date.today().isoformat(),
        "first_day": days[0].isoformat() if days else None,
        "last_day": days[-1].isoformat() if days else None,
        "dates": [d.isoformat() for d in days],
    })


# ============================================================
# RECORRIDO DIARIO
# ============================================================

def set_state(**kw):
    with state_lock:
        state.update(kw)


def run_day(day, cycle, previous):
    """
    1. Dibuja las secciones del día y arranca el visual central.
    2. Mientras el visual corre, OpenAI prepara la despedida.
    3. Al terminar el visual muestra la frase en el centro.
    4. Apaga todo y deja pasar unos segundos.
    Devuelve la frase generada (para evitar repetir la siguiente).
    """
    data = read_day(day)
    thoughts = data.pop("_thoughts")

    print(
        f"[ANTOLOGÍA] {day.isoformat()}  entradas={data['entries']}  "
        f"pensamientos={len(thoughts)}  oído={len(data['words'])}  "
        f"localizaciones={len(data['locations'])}"
    )

    payload = {"type": "day", "cycle": cycle, **data}
    set_state(mode="visual", day=payload, phrase=None, cycle=cycle)
    broadcast(payload)

    # Siempre se genera la despedida, haya o no pensamientos ese día.
    future = executor.submit(generate_farewell, thoughts, day, previous, data)

    time.sleep(VISUAL_SECONDS)

    farewell = None
    if future is not None:
        try:
            farewell = future.result(timeout=60)
        except Exception as exc:
            print(f"[OPENAI] Sin frase: {exc}")

    if farewell:
        phrase_payload = {"type": "phrase", "cycle": cycle, **farewell}
        set_state(mode="phrase", phrase=phrase_payload)
        broadcast(phrase_payload)
        time.sleep(PHRASE_SECONDS)

    set_state(mode="interlude", phrase=None)
    broadcast({"type": "interlude", "cycle": cycle})
    time.sleep(INTERLUDE_SECONDS)

    return farewell or previous


def anthology_loop():
    """Primer día -> ... -> último día -> vuelve al primero."""
    previous = None
    cycle = 0

    while True:
        days = list_log_days()

        if not days:
            print(f"[ANTOLOGÍA] No hay logs en {LOG_DIR}")
            set_state(mode="idle", day=None, phrase=None)
            broadcast({"type": "empty", "log_dir": str(LOG_DIR)})
            time.sleep(10)
            continue

        for day in days:
            try:
                previous = run_day(day, cycle, previous)
            except Exception as exc:
                print(f"[ANTOLOGÍA] Error en {day}: {type(exc).__name__}: {exc}")
                time.sleep(5)

        cycle += 1
        print("[ANTOLOGÍA] Fin del recorrido. Regresando al primer día.")


if __name__ == "__main__":
    print("")
    print("==============================================")
    print(" MACCO — ANTOLOGÍA DIARIA")
    print("==============================================")
    print(f"LOG_DIR        : {LOG_DIR}")
    print(f"OPENAI_MODEL   : {OPENAI_MODEL}")
    print(f"VISUAL_SECONDS : {VISUAL_SECONDS}")
    print(f"PHRASE_SECONDS : {PHRASE_SECONDS}")
    print(f"HOST / PORT    : {HOST}:{PORT}")
    print("")

    if not os.getenv("OPENAI_API_KEY"):
        print("ADVERTENCIA: OPENAI_API_KEY no está configurada.")

    threading.Thread(target=anthology_loop, daemon=True, name="anthology").start()

    if AUDIO_ENABLED:
        threading.Thread(target=audio_loop, daemon=True, name="audio").start()

    app.run(host=HOST, port=PORT, threaded=True, debug=False, use_reloader=False)
