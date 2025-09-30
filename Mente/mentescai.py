import subprocess
import time
import re
import random
from openai import OpenAI
import os
# import luma module
from luma.core.render import canvas
from luma.oled.device import ssd1306
# libreras del sistema
import psutil

env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "offscreen"

# ---- 1. Arrancar SuperCollider (sclang) ----
sc_proc = subprocess.Popen(
    ["pw-jack","sclang"],
    stdin=subprocess.PIPE,
    text=True,
    env=env
)

time.sleep(10)
#proc=subprocess.Popen(["python3", "/home/jorge/mu_code/servo.py"])

def parens_balanced(code: str) -> bool:
    """
    Verifica si un bloque de c�digo tiene todos los par�ntesis balanceados.
    Retorna True si est�n correctos, False si hay desbalance.
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
    code = code.replace(".add;\n)\n", ".add;\n")
    code = code.replace("(\nPbind", "\nPbind")
    #code = code.replace("\n)\n(", "\n")
    #code = code.replace(")\n(", "\n")
    if not code.startswith("("):
        code = "(\n" + code
    if not code.endswith(")"):
        code = code + "\n)"
    return code

def mostrar_info(mood: str):
    """
    Muestra en la pantalla OLED el estado de �nimo, uso de CPU, temperatura y RAM.
        """
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
        draw.text((0, 0), f"Estado: {mood}", fill="white")
        draw.text((0, 15), cpu_usage, fill="white")
        draw.text((0, 30), f"Temp: {temp}", fill="white")
        draw.text((0, 45), mem_usage, fill="white")

def extract_code(text):
    """Extrae bloque de c�digo entre backticks"""
    match = re.search(r"```[\w]*\n(.*?)```", text, re.S)
    if match:
        return match.group(1).strip()
    return text.strip()

# ---- 2. Configuraci�n ----
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
time.sleep(5)

chat_history = [
    {"role": "system", "content": "Eres un generador de codigo SuperCollider sensible con cambios tonales eclecticos."}
]

passs = 1

# Posibles estados de �nimo
moods = [
    ("triste", "ritmos oscuros, ambientales y lentos"),
    ("feliz", "ritmos alegres, luminosos y melodicos"),
    ("estresado", "ritmos febriles, rapidos y tensos"),
    ("nostalgico", "texturas suaves y etereas"),
    ("enojado", "sonidos agresivos y percusivos")
]
# inicializar oled?I2C1; direcci�n 0x3c
device = ssd1306(port=1, address=0x3C)
# ---- 3. Bucle generativo ----
while True:
    # Si historial muy grande (simulaci�n de tokens), recortar
    total_chars = sum(len(m["content"]) for m in chat_history)
    if total_chars > 3000:
        chat_history = chat_history[-3:]  # conservar �ltimos 6 mensajes

    # Cada 10 mensajes, cambia+r estado de �nimo
    print(f"==== historia { len(chat_history)} ==== " )
    if len(chat_history) % 5 == 0 or passs == 1:
        mood, mood_instruction = random.choice(moods)
        mostrar_info(mood)
        system_msg = f"Eres un generador de codigo SuperCollider sensible y eclectico. con estado de animo actual: {mood}."
        user_msg = f"Genera un instrumento que exprese {mood_instruction}. Usa SynthDef + Pbind. no des explicaciones. No agregues comentarios en el codigo generado"
        chat_history[0] = {"role": "system", "content": system_msg}
        chat_history.append({"role": "user", "content": user_msg})
    else:
        prompt = (
            f"Genera en SuperCollider un nuevo instrumento ritmico ambiental que exprese {mood_instruction} "
            "que complemente una orquesta agradable con base en tus anteriores respuestas. Usa SynthDef + Pbind. "
            "Debe definir un SynthDef y un patron (Pbind/Pseq/Prand) autocontenible. "
            "No repitas el nombre de SynthDef anterior. No agregues comentarios en el codigo generado"
        )
        chat_history.append({"role": "user", "content": prompt})

    # Llamada al modelo
    response = client.chat.completions.create(
        #model="gpt-3.5-turbo",
        model="gpt-4o-mini",
        messages=chat_history,
        temperature=0.7
    )

    sc_code = response.choices[0].message.content.strip()
    chat_history.append({"role": "assistant", "content": sc_code})

    # Extraer bloque SC
    match = re.search(r"```[\w]*\n(.*?)```", sc_code, re.S)
    if match:
        sc_code = match.group(1).strip()

    sc_code = sc_code.lstrip("(\n").rstrip(")\n")
    print("==== Bloque original ====")
    print(sc_code)
    # Insertar dentro de s.waitForBoot solo si es la primera vez
    sc_code = unify_blocks(sc_code)
    sc_code = sc_code.replace("\n", " ")

    if parens_balanced(sc_code):
        if passs == 1:
            sc_code = "s.waitForBoot({ " + sc_code + " });"
            passs = 2
        print("==== Nuevo bloque SC ====")
        print(sc_code)
        print("=========================")
            # Limpieza autom�tica de nodos antes de cargar
        sc_proc.stdin.write("Routine { s.sync; s.freeAll; }.play;\n")
        sc_proc.stdin.flush()
        time.sleep(5)

        # Enviar bloque a SC
        sc_proc.stdin.write(sc_code + "\n")
        sc_proc.stdin.flush()
        # Esperar antes de la siguiente iteraci�n
        time.sleep(30)
    else:
        print("?? Bloque descartado: parentesis no balanceados")
        print(sc_code)
        