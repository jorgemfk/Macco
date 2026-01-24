import subprocess
import time
import re
import random
from openai import OpenAI
import os
import redis, json
#import luma module
from luma.core.render import canvas
from luma.oled.device import ssd1306
from textwrap import wrap
# libreras del sistema
import psutil
import threading
import signal
from sys import path
#path += ['../../']
from IT8951.test_functions import *
from IT8951.display import AutoEPDDisplay
from IT8951 import constants
from PIL import ImageDraw, ImageFont
import textwrap

#os.environ["QT_QPA_PLATFORM"] = "offscreen"
# Comando base con sus posibles argumentos
#SCLANG_CMD = ["/Applications/SuperCollider.app/Contents/MacOS/sclang"]
SCLANG_CMD = ["pw-jack","sclang"]

sc_proc = None
error_count = 0
monitor_thread = None
lock = threading.Lock()
tactile_engine_loaded = False   # <<< Tcl

def start_sc():
    """Inicia el proceso SuperCollider y lanza el hilo monitor."""
    global sc_proc, monitor_thread

    sc_proc = subprocess.Popen(
        SCLANG_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Lanzar hilo monitor ligado a este nuevo proceso
    monitor_thread = threading.Thread(target=monitor_sc_output, daemon=True)
    monitor_thread.start()
    print(" SuperCollider iniciado.")

def restart_sc():
    """Reinicia SuperCollider limpiamente."""
    global sc_proc, error_count,tactile_engine_loaded
    tactile_engine_loaded = False
    print(" Reiniciando SuperCollider...")

    try:
        if sc_proc and sc_proc.poll() is None:
            # Enviar SIGTERM y esperar cierre limpio
            sc_proc.terminate()
            try:
                sc_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Si no se apaga, forzar
                sc_proc.kill()
    except Exception as e:
        print(f"Error al cerrar SC: {e}")

    error_count = 0
    time.sleep(5)
    start_sc()


def monitor_sc_output():
    """Hilo que monitorea la salida de SuperCollider en el proceso actual."""
    global error_count
    current_proc = sc_proc  # Captura proceso actual

    for line in current_proc.stdout:
        if current_proc.poll() is not None:
            break  # Proceso terminó
        line = line.strip()
        if not line:
            continue

        print(f"[SC] {line}")

        if "FAILURE" in line or "CRITICAL" in line:
            print(" Detectado 'FAILURE', reiniciando SC.")
            restart_sc()
            break

        if "ERROR" in line or "-> nil" in line:
            with lock:
                error_count += 1
                print(f" Error detectado ({error_count}/3)")
                if error_count >= 3:
                    print(" 3 errores acumulados, reiniciando SC.")
                    restart_sc()
                    break

# ==============================
# SC tactil engine (MEMORIA)
# ==============================
TACTILE_SC_ENGINE = r"""
(
~layers = IdentityDictionary.new;
~lastTouch = IdentityDictionary.new;

SynthDef(\touchLayer, { |out=0, freq=200, amp=0.2, pan=0|
	var env = EnvGen.kr(Env.asr(3, 1, 14), doneAction:2);
	var sig = SinOsc.ar(freq) * env * amp;
	Out.ar(out, Pan2.ar(sig, pan));
}).add;

~pinToSound = { |pin|
	switch(pin,
		20, { [80, 0.35, -0.5, 22] },   // grave
		21, { [900, 0.18, 0.5] },  // agudo
		22, { [320, 0.12, 0] },    // suave
		23, { [1200, 0.08, 0.2] },
		{ [200, 0.1, 0] })};

~touch = { |pin|
	var params = ~pinToSound.(pin);
	var now = SystemClock.seconds;
	~lastTouch[pin] = now;

	if(~layers[pin].isNil) {
		~layers[pin] = Synth(
			\touchLayer,
			[\freq, params[0], \amp, params[1], \pan, params[2]]
		);
	} {
		~layers[pin].set(\amp, params[1]);
	};

	Routine {
		18.wait;
		if(SystemClock.seconds - ~lastTouch[pin] > 16) {
			~layers[pin].free;
			~layers.removeAt(pin);
		}
	}.play;
};
)
"""
def ensure_tactile_engine():
    global tactile_engine_loaded
    if not tactile_engine_loaded:
        sc_code = unify_blocks(TACTILE_SC_ENGINE)
        print(sc_code)
        sc_proc.stdin.write("s.waitForBoot({( " + sc_code + " )});\n")
        sc_proc.stdin.flush()
        tactile_engine_loaded = True
        print(" Motor tactil con memoria cargado.")

# ---- 1. Arrancar SuperCollider (sclang) ----
start_sc()
# ---- 1. subscripcion a redis ----
r = redis.Redis(host='localhost', port=6379, db=0)
pubsub = r.pubsub()
pubsub.subscribe("emociones")

def remove_unbalanced_parens(code: str) -> str:
    """
    Elimina parentesis () y llaves {} huerfanas en codigo SuperCollider.
    Mantiene el resto del codigo intacto.
    """
    result = []
    stack = []  # guarda (caracter de apertura, indice en result)

    opening = "({"
    closing = ")}"
    pairs = {")": "(", "}": "{"}

    for ch in code:
        if ch in opening:
            stack.append((ch, len(result)))
            result.append(ch)
        elif ch in closing:
            if stack and stack[-1][0] == pairs[ch]:
                stack.pop()
                result.append(ch)
            else:
                # huérfano → lo ignoramos
                continue
        else:
            result.append(ch)

    # eliminar los que quedaron abiertos sin cerrar
    while stack:
        _, pos = stack.pop()
        result[pos] = ""

    return "".join(result)

def parens_balanced(code: str) -> bool:
    """
    Verifica si un bloque de codigo tiene todos los parentesis balanceados.
    Retorna True si estan correctos, False si hay desbalance.
    """
    stack = []
    for ch in code:
        if ch == "(":
            stack.append(ch)
        elif ch == ")":
            if not stack:
                return False  # hay un ")" sin "(" previo
            stack.pop()
    return len(stack) == 0

def unify_blocks(code: str) -> str:
    """Une SynthDef + Pbind en un solo bloque ( ... ) para SC."""
    code = code.strip()
    code = re.sub(
        r'(?m)^[ \t]*```[^\n]*\n.*?^[ \t]*```[ \t]*\n?',
        '',
        code,
        flags=re.DOTALL | re.MULTILINE
    )

    # 2) Quitar cualquier comentario de una sola línea que empiece con //
    code = re.sub(r'(?m)//.*$', '', code)

    # 3) Si quedó alguna línea con solo ``` (p. ej. bloque abierto sin cerrar), quitarla
    code = re.sub(r'(?m)^[ \t]*```.*$', '', code)
    code = re.sub(r"```.*?```", "", code, flags=re.DOTALL)
    code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'(?m)^[ \t]*[()] *$', '', code)
    code = code.replace("\n", " ")
    return code

def mostrar_info(mood: str):

    #Muestra en la pantalla OLED el estado de animo, uso de CPU, temperatura y RAM.

    # obtener datos del sistema
    cpu_usage = f"CPU: {psutil.cpu_percent()} %"
    mem = psutil.virtual_memory()
    mem_usage = f"RAM: {mem.percent} %"

    # leer temperatura (ejemplo en Raspberry Pi)
    try:
        temp = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        temp = temp.replace("temp=", "").strip()
    except Exception:
        temp = "N/A"

    # mostrar en OLED
    with canvas(device) as draw:
        max_width = 20
        lines = wrap(mood, width=max_width)
        y = 0
        for line in lines:
            draw.text((0, y), line, fill="white")
            y += 10
    #with canvas(device) as draw:
        #draw.text((0, 0), f"{mood}", fill="white")
        #draw.text((0, 15), cpu_usage, fill="white")
        #draw.text((0, 30), f"Temp: {temp}", fill="white")
        #draw.text((0, 45), mem_usage, fill="white")
#display de papel        
EMOTION_ANIMATORS = {
    "Enojo": "animate_angry",
    "Asco": "animate_disgust",
    "Miedo": "animate_fear",
    "Felicidad": "animate_happy",
    "Tristeza": "animate_sad",
    "Sorpresa": "animate_surprise",
    "Neutral": "animate_neutral",
}

from PIL import ImageDraw

def clear_face_area(img, cx, cy, size):
    img.paste(
        0xFF,
        (cx-size, cy-size, cx+size, cy+size)
    )


def draw_eyes(draw, cx, cy, dx, dy, r):
    draw.ellipse((cx-dx-r, cy-dy-r, cx-dx+r, cy-dy+r), fill=0)
    draw.ellipse((cx+dx-r, cy-dy-r, cx+dx+r, cy-dy+r), fill=0)


def draw_mouth_line(draw, cx, y, w, thickness=3):
    draw.line((cx-w, y, cx+w, y), fill=0, width=thickness)


def draw_mouth_circle(draw, cx, cy, r, fill=False):
    if fill:
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=0)
    else:
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=0, width=3)


def draw_smile(draw, cx, cy, w, h):
    draw.arc((cx-w, cy-h, cx+w, cy+h), 0, 180, fill=0, width=3)


def draw_frown(draw, cx, cy, w, h):
    draw.arc((cx-w, cy, cx+w, cy+h), 180, 360, fill=0, width=3)

import time

def animate_surprise(display, cx, cy, size=70, delay=0.25):
    img = display.frame_buf
    d = ImageDraw.Draw(img)

    frames = [
        {"eye_r": 5, "mouth": "line"},
        {"eye_r": 8, "mouth": "circle"},
        {"eye_r": 10, "mouth": "circle"},
        {"eye_r": 8, "mouth": "line"},
    ]

    for f in frames:
        clear_face_area(img, cx, cy, size)

        draw_eyes(d, cx, cy, dx=25, dy=20, r=f["eye_r"])

        if f["mouth"] == "line":
            draw_mouth_line(d, cx, cy+25, w=15)
        else:
            draw_mouth_circle(d, cx, cy+25, r=10)

        display.draw_partial(constants.DisplayModes.DU)
        time.sleep(delay)
def animate_happy(display, cx, cy, size=70, delay=0.3):
    img = display.frame_buf
    d = ImageDraw.Draw(img)

    frames = [
        {"eye_open": True,  "smile_h": 12},
        {"eye_open": False, "smile_h": 18},
        {"eye_open": True,  "smile_h": 22},
    ]

    for f in frames:
        clear_face_area(img, cx, cy, size)

        if f["eye_open"]:
            draw_eyes(d, cx, cy, dx=25, dy=20, r=5)
        else:
            # ojos cerrados (curva)
            d.arc((cx-35, cy-20, cx-15, cy-10), 0, 180, fill=0, width=3)
            d.arc((cx+15, cy-20, cx+35, cy-10), 0, 180, fill=0, width=3)

        draw_smile(d, cx, cy+25, w=30, h=f["smile_h"])

        display.draw_partial(constants.DisplayModes.DU)
        time.sleep(delay)
def animate_neutral(display, cx, cy, size=70, delay=0.5):
    img = display.frame_buf
    d = ImageDraw.Draw(img)

    for _ in range(2):
        clear_face_area(img, cx, cy, size)
        draw_eyes(d, cx, cy, dx=25, dy=20, r=5)
        draw_mouth_line(d, cx, cy+25, w=20)
        display.draw_partial(constants.DisplayModes.DU)
        time.sleep(delay)

def draw_text_centered_autosize(
    img,
    text,
    max_width_px,
    max_height_px,
    max_fontsize=72,
    min_fontsize=28,
    line_spacing_ratio=0.25
):
    draw = ImageDraw.Draw(img)

    try:
        font_path = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
        ImageFont.truetype(font_path, 10)
    except OSError:
        font_path = "/usr/share/fonts/TTF/DejaVuSans.ttf"

    img_w, img_h = img.size

    for fontsize in range(max_fontsize, min_fontsize - 1, -2):
        font = ImageFont.truetype(font_path, fontsize)

        avg_char_width = sum(font.getlength(c) for c in "abcdefghijklmnopqrstuvwxyz") / 26
        max_chars = int(max_width_px / avg_char_width)

        lines = textwrap.wrap(text, width=max_chars)

        line_spacing = int(fontsize * line_spacing_ratio)

        total_height = 0
        max_line_width = 0

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            max_line_width = max(max_line_width, w)
            total_height += h

        total_height += line_spacing * (len(lines) - 1)

        if max_line_width <= max_width_px and total_height <= max_height_px:
            break

    start_y = (img_h - total_height) // 2

    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (img_w - w) // 2
        draw.text((x, y), line, font=font, fill=0)
        y += (bbox[3] - bbox[1]) + line_spacing

        
def mostrar_info_ink(display, mood_text: str, emocion: str):
    clear_display(display)

    display.frame_buf.paste(
        0xFF, (0, 0, display.width, display.height)
    )

    # Texto: una sola vez
    draw_text_centered_autosize(
        display.frame_buf,
        mood_text,
        max_width_px=720,
        max_height_px=380,
        max_fontsize=64
    )

    display.draw_partial(constants.DisplayModes.DU)

    # Cara animada
    cx = display.width // 2
    cy = 110

    animator_name = EMOTION_ANIMATORS.get(emocion, "animate_neutral")
    animator = globals()[animator_name]

    animator(display, cx, cy)


def extract_code(text):
    """Extrae bloque de codigo entre backticks"""
    match = re.search(r"```[\w]*\n(.*?)```", text, re.S)
    if match:
        return match.group(1).strip()
    return text.strip()

# ---- 2. Configuracion ----
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
time.sleep(5)

chat_history = [
    {"role": "system", "content": "Eres un generador de codigo SuperCollider sensible con cambios tonales eclecticos."}
]

passs = 1

# inicializar oled?I2C1; direccion 0x3c
#device = ssd1306(port=1, address=0x3C)
display = AutoEPDDisplay(vcom=-2.15, rotate='flip', mirror=None, spi_hz=24000000)
# ---- 3. Bucle generativo ----
for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"])
        print("\n Nuevo evento recibido:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
#while True:
    # Si historial muy grande (simulacion de tokens), recortar
        total_chars = sum(len(m["content"]) for m in chat_history)
        if total_chars > 8000:
            chat_history = chat_history[-3:]  # conservar ultimos 6 mensajes

        parts = re.split(r"(?<=\))\s|\n", data["respuesta_openai"], maxsplit=1)
        first_sentence = parts[0].strip() if parts else ""
        second_sentence = parts[1].strip() if len(parts) > 1 else ""

        mood = first_sentence
        mood_instruction = second_sentence
        mostrar_info_ink(display, mood, 'Felicidad')
        # ==========================
        #  CASO TACTO 
        # ==========================
        if data.get("sentido") == "tacto":
            ensure_tactile_engine()
            pin = data.get("pin", 0)
            sc_proc.stdin.write(f"~touch.value({pin});\n")
            sc_proc.stdin.flush()
            continue   # <<< no ejecuta lo siguiente

        # Cada 10 mensajes, cambia+r estado de animo
        print(f"==== historia { len(chat_history)} ==== " )
        #mood = data["emocion"]
        #mood_instruction = get_mood_description(mood)


        system_msg = f"Eres un DJ live coder Eclectico en SuperCollider 3.10, capaz de generar texturas musicales con base en emociones. Estado actual: {mood}."
        user_msg = f"""
Genera código SuperCollider (SC 3.10) con entre 5 y 7 SynthDef y patrones Pbind/Pseq/Prand
que juntos expresen {mood_instruction} con efecto estereo.

Restricciones:
- Solo puedes usar: SynthDef, SinOsc, Saw, Pulse, LFPulse, Env, EnvGen, Mix, Out, Pan2, LPF, HPF, FreeVerb, DelayN, CombN, Impulse, Dust, Pbind, Pseq, Prand, Pmono, Pdef, TempoClock.
- No inventes funciones, clases ni metodos.
- No uses  .delay().
- No incluyas comentarios ni explicaciones.
- Usa formato estandar ejemplo:
(
SynthDef(...).add;
...
Pbind(...).play;
)
El resultado debe ser expresivo y musicalmente coherente, no simple.
"""
        chat_history[0] = {"role": "system", "content": system_msg}
        chat_history.append({"role": "user", "content": user_msg})
        print(f"==== MODO { system_msg } ==== " )


        # Llamada al modelo
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_history,
            temperature=0.7
        )

        sc_code = response.choices[0].message.content.strip()
        #chat_history.append({"role": "assistant", "content": sc_code})

        # Extraer bloque SC
        match = re.search(r"```[\w]*\n(.*?)```", sc_code, re.S)
        if match:
            sc_code = match.group(1).strip()


        print("==== Bloque original ====")
        print(sc_code)
        # Insertar dentro de s.waitForBoot solo si es la primera vez
        sc_code = unify_blocks(sc_code)
        if parens_balanced(sc_code):
            sc_proc.stdin.write("s.freeAll; Pdef.all.do(_.stop); TempoClock.default.clear;\n")
            sc_proc.stdin.flush()
            time.sleep(1.5)
            sc_code = "s.waitForBoot({s.freeAll; " + sc_code + " });"

            print("==== Nuevo bloque SC ====")
            # Enviar bloque a SC
            sc_proc.stdin.write(sc_code + "\n")
            sc_proc.stdin.flush()
        else:
            print("?? Bloque descartado: parentesis no balanceados")
            print(sc_code)
            chat_history = chat_history[:-2]
