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

#os.environ["QT_QPA_PLATFORM"] = "offscreen"
# Comando base con sus posibles argumentos
SCLANG_CMD = ["/Applications/SuperCollider.app/Contents/MacOS/sclang"]
#SCLANG_CMD = ["pw-jack","sclang"]

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

        parts = re.split(r"(?<=\))\s|\n", data["respuesta_openai"], maxsplit=1)
        first_sentence = parts[0].strip() if parts else ""
        second_sentence = parts[1].strip() if len(parts) > 1 else ""

        mood = first_sentence
        mood_instruction = second_sentence

        #mood, mood_instruction = random.choice(moods)
        #mostrar_info(mood)
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
