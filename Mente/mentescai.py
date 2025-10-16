import subprocess
import time
import re
import random
from openai import OpenAI
import os
import redis, json
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
    #code = code.lstrip("(\n").rstrip(")\n")
    #remove_unbalanced_parens(code)
    #code = code.replace(".add;\n)\n", ".add;\n")
    #code = code.replace(".fork;\n)\n", ".fork;\n")
    #code = code.replace("(\nPbind", "\nPbind")
    #code = code.replace("(\nPmono", "\nPmono")
    #code = code.replace(".play;\n)\n", ".play;\n")
    #code = code.replace("\n)\n(", "\n")
    #code = code.replace(")\n(", "\n")
    #if not code.startswith("("):
    #    code = "(\n" + code
    #if not code.endswith(")"):
    #    code = code + "\n)"
    code = code.replace("\n", " ")  
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
    ("Enojo", "ritmos percusivos intensos, distorsión, bajos saturados y tempos rápidos, uso de Saw o PulseOsc para agresividad"),
    ("Asco", "texturas ruidosas, disonancias, filtros resonantes, sonidos ásperos y efectos glitch o ring modulation"),
    ("Miedo", "ambiente oscuro con drones graves, reverberación profunda, tonos inestables y ruidos modulados lentamente"),
    ("Feliz", "melodías brillantes y armónicas con ritmo animado, uso de Sine y Saw suaves, percusión ligera y arpegios ascendentes"),
    ("Triste", "tempos lentos, acordes menores, pads etéreos con reverberación, uso de SinOsc y LPF para calidez melancolica"),
    ("Sorpresa", "sonidos impredecibles, cambios abruptos de ritmo y tono, FM o Sample&Hold, percusiones irregulares"),
    ("Neutral", "ritmo constante y equilibrado, timbres suaves, balance entre ruido y tono, estructura minimalista y repetitiva")
]
def get_mood_description(nombre):
    for mood, desc in moods:
        if mood.lower() == nombre.lower():
            return desc
    return "No se encontró ese mood."
# inicializar oled?I2C1; direccion 0x3c
#device = ssd1306(port=1, address=0x3C)
# ---- 3. Bucle generativo ----
for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"])
        print("\n📢 Nuevo evento recibido:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
#while True:
    # Si historial muy grande (simulacion de tokens), recortar
        total_chars = sum(len(m["content"]) for m in chat_history)
        if total_chars > 4000:
            chat_history = chat_history[-3:]  # conservar ultimos 6 mensajes

        # Cada 10 mensajes, cambia+r estado de animo
        print(f"==== historia { len(chat_history)} ==== " )
        mood = data["emocion"]
        mood_instruction = get_mood_description(mood)
        #mood, mood_instruction = random.choice(moods)
    #        mostrar_info(mood)
        system_msg = f"Eres un dj live coder  de codigo SuperCollider version 3.10 sensible y eclectico. con estado de animo actual: {mood}."
        user_msg = f"Genera 5 instrumentos o beat que juntos formen una melodia que exprese {mood_instruction} con SynthDef y un patron (Pbind/Pseq/Prand) . no des explicaciones. No agregues comentarios en el codigo generado. No inventes funciones tampoco clases, no uses .delay(). no uses archivos wav externos con Buffer.read"
        chat_history[0] = {"role": "system", "content": system_msg}
        chat_history.append({"role": "user", "content": user_msg})
        print(f"==== MODO { mood } ==== " )


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
        if parens_balanced(sc_code):
            #if passs == 1  :
            #    if "s.boot" not in sc_code and "s.waitForBoot" not in sc_code:
            #        sc_code = "s.waitForBoot({s.freeAll; " + sc_code + " });"
            #    passs = 2
            #else :
            #    sc_code = "(" + sc_code
            #    sc_code = sc_code + ")"
            sc_code = "s.waitForBoot({s.freeAll; " + sc_code + " });"
            
            print("==== Nuevo bloque SC ====")
            print(sc_code)
            print("=========================")
                # Limpieza automatica de nodos antes de cargar
            #sc_proc.stdin.write("Routine { s.sync; s.freeAll; }.play;")
            #sc_proc.stdin.write("s.freeAll;")     
            #sc_proc.stdin.flush()
            #time.sleep(5)

            # Enviar bloque a SC
            sc_proc.stdin.write(sc_code + "\n")
            sc_proc.stdin.flush()
            # Esperar antes de la siguiente iteracion
            #time.sleep(3)
        else:
            print("?? Bloque descartado: parentesis no balanceados")
            print(sc_code)
            chat_history = chat_history[:-2] 
        
