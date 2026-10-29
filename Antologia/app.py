import os
import json
import re
import time
import threading
from datetime import datetime, date, timedelta
from pathlib import Path

from flask import Flask, render_template, jsonify
from flask_sock import Sock
from openai import OpenAI

# ============================================================
# CONFIGURACIÓN
# ============================================================

LOG_DIR = Path(os.getenv("MACCO_LOG_DIR", "/home/jorge/logMacco"))
HOST = os.getenv("MACCO_HOST", "0.0.0.0")
PORT = int(os.getenv("MACCO_PORT", "8080"))

# Modelo económico para generación de texto.
# Se puede cambiar con:
# export OPENAI_MODEL="gpt-5.6-luna"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

# Tiempo visible de cada frase y duración de la transición.
PHRASE_SECONDS = float(os.getenv("MACCO_PHRASE_SECONDS", "12"))
INTERLUDE_SECONDS = float(os.getenv("MACCO_INTERLUDE_SECONDS", "5"))

app = Flask(__name__)
sock = Sock(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Clientes WebSocket conectados.
clients = set()
clients_lock = threading.Lock()

# Estado público.
state_lock = threading.Lock()
state = {
    "mode": "interlude",
    "text": "",
    "emotion": "Neutral",
    "date": "",
    "cycle": 0,
    "connected_clients": 0,
    "source_thoughts": 0,
}

EMOTIONS = [
    "Tristeza",
    "Nostalgia",
    "Miedo",
    "Deseo",
    "Ansiedad",
    "Curiosidad",
    "Fascinación",
    "Rechazo",
    "Ternura",
    "Vergüenza",
    "Soledad",
    "Alivio",
    "Inquietud",
    "Asombro",
    "Calma",
    "Esperanza",
]

# ============================================================
# LECTURA DE MEMORIA
# ============================================================

def parse_log_date(path: Path):
    """
    Espera archivos YYYY-MM-DD.log.
    """
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.log", path.name)
    if not match:
        return None

    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def read_thoughts_for_date(day: date):
    """
    Lee únicamente registros:
        {"sentido":"pensamiento", "fecha":..., "pensamiento":...}
    del archivo diario.
    """
    path = LOG_DIR / f"{day.isoformat()}.log"

    if not path.exists():
        return []

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

                if item.get("sentido") != "pensamiento":
                    continue

                thought = str(item.get("pensamiento", "")).strip()

                if thought:
                    thoughts.append({
                        "fecha": item.get("fecha", day.isoformat()),
                        "pensamiento": thought,
                    })

    except OSError as exc:
        print(f"[LOG] No se pudo leer {path}: {exc}")

    return thoughts


def available_thought_dates():
    """
    Construye la antología desde HOY hacia atrás, hasta la fecha
    más antigua que tenga al menos un pensamiento.

    Los días sin pensamientos se omiten: no se inventa una fuente
    histórica inexistente.
    """
    if not LOG_DIR.exists():
        return []

    days = []

    for path in LOG_DIR.glob("*.log"):
        d = parse_log_date(path)
        if d is None:
            continue

        # No usamos fechas futuras.
        if d > date.today():
            continue

        thoughts = read_thoughts_for_date(d)
        if thoughts:
            days.append(d)

    return sorted(set(days), reverse=True)


def latest_thought_date():
    days = available_thought_dates()
    return days[-1] if days else None


# ============================================================
# OPENAI
# ============================================================

SYSTEM_PROMPT = """
Eres la voz antológica de MACCO, una instalación artística que ha
acumulado pensamientos durante meses.

Recibes los pensamientos que MACCO produjo durante UN DÍA concreto.

Tu tarea NO es resumirlos literalmente.

Debes transformarlos en una nueva pieza breve: una frase que parezca
haber nacido de la memoria de ese día.

La frase debe ser:
- íntima
- intensa
- extraña
- emocional
- concreta
- ligeramente ambigua
- diferente de las frases anteriores
- adecuada para ser proyectada en una sala de exposición

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
deseo y rechazo,
memoria y olvido,
curiosidad y miedo,
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

Máximo 35 palabras para la frase.
"""


def extract_json(text):
    """
    Tolerancia ante modelos que devuelvan ```json ... ``` o texto extra.
    """
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        text = text[start:end + 1]

    return json.loads(text)


def generate_anthology(thoughts, day, previous=None):
    """
    Genera una nueva frase incluso si se ejecuta varias veces sobre
    el mismo día. Los pensamientos históricos son la materia prima;
    la frase es siempre nueva.
    """

    source = "\n".join(
        f"- {item['pensamiento']}"
        for item in thoughts[-80:]
    )

    previous_text = ""
    if previous:
        previous_text = f"""
Frase antológica inmediatamente anterior:
"{previous['frase']}"

No la reformules ni repitas su idea.
"""

    user_prompt = f"""
Fecha de la memoria: {day.isoformat()}

Pensamientos originales de ese día:
{source}

{previous_text}

Crea una nueva frase antológica para ese día.
No la copies. No la resumas.
"""

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
            max_output_tokens=160,
        )

        raw = response.output_text.strip()
        data = extract_json(raw)

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
            "fuente_pensamientos": len(thoughts),
            "modelo": OPENAI_MODEL,
        }

    except Exception as exc:
        print(f"[OPENAI] Error: {type(exc).__name__}: {exc}")

        # Fallback: no detiene la instalación si temporalmente falla la API.
        fallback = thoughts[-1]["pensamiento"]

        return {
            "frase": fallback,
            "sentimiento": "Neutral",
            "fecha": day.isoformat(),
            "fuente_pensamientos": len(thoughts),
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

    try:
        # Mantener la conexión abierta.
        while True:
            message = ws.receive()

            if message is None:
                break

            # El navegador puede mandar "ping" si se desea.
            if message == "ping":
                try:
                    ws.send("pong")
                except Exception:
                    break

    except Exception as exc:
        print(f"[WS] conexión terminada: {exc}")

    finally:
        with clients_lock:
            clients.discard(ws)
            with state_lock:
                state["connected_clients"] = len(clients)

        print("[WS] cliente desconectado")


# ============================================================
# WEB
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    with state_lock:
        result = dict(state)

    result["today"] = date.today().isoformat()
    result["available_dates"] = [
        d.isoformat() for d in available_thought_dates()
    ]

    return jsonify(result)


@app.route("/api/scan")
def api_scan():
    days = available_thought_dates()

    return jsonify({
        "log_dir": str(LOG_DIR),
        "today": date.today().isoformat(),
        "oldest_thought_date": days[-1].isoformat() if days else None,
        "dates": [d.isoformat() for d in days],
    })


# ============================================================
# ANTOLOGÍA
# ============================================================

def anthology_loop():
    """
    Recorre:

        hoy -> ayer -> ... -> fecha más antigua con pensamientos

    Al terminar, vuelve a HOY.

    Cada visita al mismo día vuelve a llamar a OpenAI, por lo que
    la frase antológica no es una reproducción fija.
    """

    previous = None
    cycle = 0

    while True:

        days = available_thought_dates()

        if not days:
            print("[ANTOLOGÍA] No hay pensamientos todavía.")
            time.sleep(10)
            continue

        # Intermedio inicial.
        broadcast({
            "type": "interlude",
            "emotion": "Neutral",
            "date": "",
            "text": "",
            "cycle": cycle,
        })

        for day in days:

            thoughts = read_thoughts_for_date(day)

            if not thoughts:
                continue

            print(
                f"[ANTOLOGÍA] {day.isoformat()} "
                f"({len(thoughts)} pensamientos)"
            )

            # Generativa: siempre genera una frase nueva.
            item = generate_anthology(
                thoughts=thoughts,
                day=day,
                previous=previous
            )

            previous = item

            with state_lock:
                state.update({
                    "mode": "phrase",
                    "text": item["frase"],
                    "emotion": item["sentimiento"],
                    "date": item["fecha"],
                    "cycle": cycle,
                    "source_thoughts": item["fuente_pensamientos"],
                })

            broadcast({
                "type": "phrase",
                **item,
                "cycle": cycle,
            })

            time.sleep(PHRASE_SECONDS)

            # Intermedio ASCII antes de la siguiente frase.
            with state_lock:
                state["mode"] = "interlude"

            broadcast({
                "type": "interlude",
                "emotion": item["sentimiento"],
                "date": item["fecha"],
                "text": "",
                "cycle": cycle,
            })

            time.sleep(INTERLUDE_SECONDS)

        # Terminó el recorrido histórico.
        # Volverá a consultar los logs: si aparecieron nuevos días,
        # se incorporarán automáticamente.
        cycle += 1
        print("[ANTOLOGÍA] Fin del recorrido. Regresando a hoy.")


if __name__ == "__main__":
    print("")
    print("==============================================")
    print(" MACCO — ANTOLOGÍA DIARIA")
    print("==============================================")
    print(f"LOG_DIR      : {LOG_DIR}")
    print(f"OPENAI_MODEL : {OPENAI_MODEL}")
    print(f"HOST         : {HOST}")
    print(f"PORT         : {PORT}")
    print("")
    print(f"URL: http://<IP_RASPBERRY>:{PORT}")
    print("")

    if not os.getenv("OPENAI_API_KEY"):
        print("ADVERTENCIA: OPENAI_API_KEY no está configurada.")

    worker = threading.Thread(
        target=anthology_loop,
        daemon=True,
        name="anthology-loop",
    )
    worker.start()

    # Flask-Sock usa WebSocket nativo; no hay Socket.IO ni CDN.
    app.run(
        host=HOST,
        port=PORT,
        threaded=True,
        debug=False,
        use_reloader=False,
    )
