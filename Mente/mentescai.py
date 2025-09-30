import subprocess
import time
import re
import random
from openai import OpenAI
import os
# import luma module
#from luma.core.render import canvas
#from luma.oled.device import ssd1306
# libreras del sistema
#import psutil


# ---- 1. Arrancar SuperCollider (sclang) ----
sc_proc = subprocess.Popen(
    ["/Applications/SuperCollider.app/Contents/MacOS/sclang"],
    stdin=subprocess.PIPE,
    text=True
)
time.sleep(15)

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
    code = code.lstrip("(\n").rstrip(")\n")
    #remove_unbalanced_parens(code)
    code = code.replace(".add;\n)\n", ".add;\n")
    code = code.replace(".fork;\n)\n", ".fork;\n")
    code = code.replace("(\nPbind", "\nPbind")
    code = code.replace("(\nPmono", "\nPmono")
    code = code.replace(".play;\n)\n", ".play;\n")
    #code = code.replace("\n)\n(", "\n")
    #code = code.replace(")\n(", "\n")
    if not code.startswith("("):
        code = "(\n" + code
    if not code.endswith(")"):
        code = code + "\n)"
    return code
"""
def mostrar_info(mood: str):
    
    Muestra en la pantalla OLED el estado de animo, uso de CPU, temperatura y RAM.
        
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
"""
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

# Posibles estados de animo
moods = [
    ("triste", "beats oscuros, ambientales y lentos"),
    ("feliz", "beats alegres, luminosos y melodicos"),
    ("estresado", "beats febriles, rapidos y tensos"),
    ("nostalgico", "ritmos texturas suaves y etereas"),
    ("enojado", "tambores sonidos agresivos y percusivos")
]
# inicializar oled?I2C1; direccion 0x3c
#device = ssd1306(port=1, address=0x3C)
# ---- 3. Bucle generativo ----
while True:
    # Si historial muy grande (simulacion de tokens), recortar
    total_chars = sum(len(m["content"]) for m in chat_history)
    if total_chars > 4000:
        chat_history = chat_history[-3:]  # conservar ultimos 6 mensajes

    # Cada 10 mensajes, cambia+r estado de animo
    print(f"==== historia { len(chat_history)} ==== " )
    if len(chat_history) % 5 == 0 or passs == 1:
        mood, mood_instruction = random.choice(moods)
#        mostrar_info(mood)
        system_msg = f"Eres un dj live coder  de codigo SuperCollider sensible y eclectico. con estado de animo actual: {mood}."
        user_msg = f"Genera un instrumento o beat finito (tu decide el tipo y tiempo de duracion) formando una melodia que exprese {mood_instruction}. no des explicaciones. No agregues comentarios en el codigo generado"
        chat_history[0] = {"role": "system", "content": system_msg}
        chat_history.append({"role": "user", "content": user_msg})
        print(f"==== MODO { mood } ==== " )
        if passs == 2 :
            sc_proc.stdin.write("s.record;2.wait;")
            sc_proc.stdin.flush()
            time.sleep(5)
            sc_proc.stdin.write("s.stopRecording;")
            sc_proc.stdin.flush()
    else:
        prompt = (
            f"Genera en SuperCollider un nuevo instrumento ritmico ambiental que exprese {mood_instruction} "
            "que complemente una orquesta agradable con base en tus anteriores respuestas. "
            "Debe definir un SynthDef y un patron (Pbind/Pseq/Prand) autocontenible finito (tu decide el tipo y tiempo de duracion) . "
            "No repitas el nombre de SynthDef anterior. No agregues comentarios en el codigo generado"
        )
        chat_history.append({"role": "user", "content": prompt})

    # Llamada al modelo
    response = client.chat.completions.create(
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

    
    print("==== Bloque original ====")
    print(sc_code)
    # Insertar dentro de s.waitForBoot solo si es la primera vez
    sc_code = unify_blocks(sc_code)
    sc_code = sc_code.replace("\n", " ")
    
    if parens_balanced(sc_code):
        if passs == 1  :
            if "s.boot" not in sc_code and "s.waitForBoot" not in sc_code:
                sc_code = "s.waitForBoot({ " + sc_code + " });"
            passs = 2
        print("==== Nuevo bloque SC ====")
        print(sc_code)
        print("=========================")
            # Limpieza automatica de nodos antes de cargar
        sc_proc.stdin.write("Routine { s.sync; s.freeAll; }.play;")
        sc_proc.stdin.flush()
        time.sleep(5)

        # Enviar bloque a SC
        sc_proc.stdin.write(sc_code + "\n")
        sc_proc.stdin.flush()
        # Esperar antes de la siguiente iteracion
        time.sleep(30)
    else:
        print("?? Bloque descartado: parentesis no balanceados")
        print(sc_code)
        chat_history = chat_history[:-2] 
    