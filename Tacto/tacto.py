# coding:utf-8
import socket
import time
import threading
import queue
import requests
import warnings
import math
import random

import RPi.GPIO as GPIO
from gpiozero import DistanceSensor, PWMSoftwareFallback, DistanceSensorNoEcho
from pca9685 import PCA9685

# =============================
# CONFIG
# =============================
SERVER_IP = "127.0.0.1"
CMD_PORT = 5002

# Touch
TOUCH_PINS = [21, 25, 20, 12]
TACTO_SERVER = "http://192.168.0.82:5822/touch"

# Ultrasonicos
ULTRASONICS = [
    {"trigger": 27, "echo": 22, "name": "front"},  # servo canal 1
    {"trigger": 33, "echo": 35, "name": "left"},   # fijo X-
    {"trigger": 37, "echo": 36, "name": "right"},  # fijo X+
    {"trigger": 29, "echo": 31, "name": "rear"},   # servo canal 2
]

MAX_DISTANCE = 3.0         # metros
MAX_DISTANCE_CM = 300.0
OBSTACLE_CM = 25.0
RECHECK_INTERVAL = 0.12    # evita saturar server

# =============================
# SERVOS DE ULTRASONIC
# front = canal 1
# rear  = canal 2
# =============================
FRONT_SERVO_CHANNEL = 1
REAR_SERVO_CHANNEL = 2

SERVO_CENTER = 45
SERVO_MIN = 0
SERVO_MAX = 90

# Para front:
# 45 = Y+
# <45 = sesgo X-
# >45 = sesgo X+
#
# Para rear:
# 45 = Y-
# <45 = sesgo X+
# >45 = sesgo X-
#
# (porque está “viendo hacia atrás”, invertido respecto a front)

# =============================
# LÍMITES MOVIMIENTO ROBOT
# =============================
MAX_AXIS = 15
MAX_STEPS = 10

# =============================
# PERSONALIDAD POR TOUCH PIN
# =============================
TOUCH_BEHAVIOR = {
    21: {
        "name": "curioso",
        "base_speed": 8,
        "steps": 6,
        "jitter": 2,
        "explore": 1.0,
        "shake": [
            "CMD_POSITION#4#-2#0",
            "CMD_POSITION#3#1#0",
            "CMD_POSITION#-2#2#0",
            "CMD_POSITION#0#0#0",
        ],
    },
    25: {
        "name": "nervioso",
        "base_speed": 11,
        "steps": 9,
        "jitter": 4,
        "explore": 1.4,
        "shake": [
            "CMD_POSITION#-3#0#0",
            "CMD_POSITION#3#0#0",
            "CMD_POSITION#-2#1#0",
            "CMD_POSITION#0#0#0",
        ],
    },
    20: {
        "name": "cauto",
        "base_speed": 6,
        "steps": 4,
        "jitter": 1,
        "explore": 0.8,
        "shake": [
            "CMD_POSITION#0#3#0",
            "CMD_POSITION#0#-2#0",
            "CMD_POSITION#1#1#0",
            "CMD_POSITION#0#0#0",
        ],
    },
    12: {
        "name": "erratico",
        "base_speed": 9,
        "steps": 10,
        "jitter": 5,
        "explore": 1.8,
        "shake": [
            "CMD_POSITION#2#2#0",
            "CMD_POSITION#-2#-2#0",
            "CMD_POSITION#2#-1#0",
            "CMD_POSITION#0#0#0",
        ],
    },
}

# =============================
# GPIO SETUP
# =============================
GPIO.setmode(GPIO.BCM)
for pin in TOUCH_PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# =============================
# ULTRASONIC CLASS
# =============================
class Ultrasonic:
    def __init__(self, trigger_pin: int, echo_pin: int, max_distance: float = 3.0):
        warnings.filterwarnings("ignore", category=DistanceSensorNoEcho)
        warnings.filterwarnings("ignore", category=PWMSoftwareFallback)

        self.sensor = DistanceSensor(
            trigger=trigger_pin,
            echo=echo_pin,
            max_distance=max_distance
        )

    def get_distance(self):
        try:
            return round(self.sensor.distance * 100, 1)
        except RuntimeWarning:
            return None
        except Exception:
            return None

    def close(self):
        self.sensor.close()

# =============================
# SERVO PCA9685
# =============================
def map_value(value, from_low, from_high, to_low, to_high):
    return (to_high - to_low) * (value - from_low) / (from_high - from_low) + to_low

class Servo:
    def __init__(self):
        self.pwm_40 = PCA9685(0x40, debug=False)
        self.pwm_41 = PCA9685(0x41, debug=False)
        self.pwm_40.set_pwm_freq(50)
        self.pwm_41.set_pwm_freq(50)
        time.sleep(0.02)

    def set_angle(self, channel, angle):
        angle = max(0, min(180, angle))
        duty = map_value(angle, 0, 180, 500, 2500)
        duty = map_value(duty, 0, 20000, 0, 4095)

        if channel < 16:
            self.pwm_41.set_pwm(channel, 0, int(duty))
        else:
            self.pwm_40.set_pwm(channel - 16, 0, int(duty))

    def relax(self):
        for i in range(16):
            self.pwm_41.set_pwm(i, 4096, 4096)
            self.pwm_40.set_pwm(i, 4096, 4096)

servo = Servo()

# =============================
# TACTO ASYNC
# =============================
tacto_queue = queue.Queue()

def tacto_worker():
    while True:
        pin = tacto_queue.get()
        if pin is None:
            break
        try:
            requests.post(TACTO_SERVER, json={"pin": pin}, timeout=0.3)
        except Exception as e:
            print("⚠ tacto server:", e)
        tacto_queue.task_done()

threading.Thread(target=tacto_worker, daemon=True).start()

def notify_tacto_server(pin):
    tacto_queue.put(pin)

# =============================
# ULTRASONIC SETUP
# =============================
ultrasonics = {
    cfg["name"]: Ultrasonic(cfg["trigger"], cfg["echo"], MAX_DISTANCE)
    for cfg in ULTRASONICS
}

# Estado de distancias
distances_state = {
    "front": None,
    "left": None,
    "right": None,
    "rear": None,
}

# Estado de ángulos
servo_angles = {
    "front": SERVO_CENTER,
    "rear": SERVO_CENTER,
}

touch_active = False

# =============================
# SOCKET MOVIMIENTO
# =============================
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((SERVER_IP, CMD_PORT))
print("Cliente movimiento conectado")

# =============================
# HELPERS
# =============================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def send_cmd(cmd):
    if not cmd.endswith("\n"):
        cmd += "\n"
    sock.send(cmd.encode())

def send_move(x, y, steps=8):
    x = int(clamp(round(x), -MAX_AXIS, MAX_AXIS))
    y = int(clamp(round(y), -MAX_AXIS, MAX_AXIS))
    steps = int(clamp(steps, 1, MAX_STEPS))
    cmd = f"CMD_MOVE#1#{x}#{y}#{steps}#0"
    send_cmd(cmd)
    print("➡", cmd)

def send_stop():
    send_cmd("CMD_MOVE#1#0#0#8#0")
    print("⏹ STOP")

def send_position(x, y):
    x = int(clamp(round(x), -15, 15))
    y = int(clamp(round(y), -15, 15))
    cmd = f"CMD_POSITION#{x}#{y}#0"
    send_cmd(cmd)
    print("💃", cmd)

def do_shake_for_touch(pin):
    behavior = TOUCH_BEHAVIOR.get(pin)
    if not behavior:
        return
    for cmd in behavior["shake"]:
        send_cmd(cmd)
        print("💃", cmd)
        time.sleep(0.12)

# =============================
# CONVERSIÓN DE DISTANCIA A PESO
# más distancia = más "atracción" hacia esa dirección
# si está muy cerca del obstáculo = casi nulo
# =============================
def distance_to_weight(d):
    if d is None or d <= 0:
        return None

    # si está muy cerca, casi no aporta
    if d <= OBSTACLE_CM:
        return 0.05

    # normaliza aprox 0..1 usando 120 cm como zona útil
    usable = clamp((d - OBSTACLE_CM) / 120.0, 0.0, 1.0)

    # curva un poco más orgánica
    return 0.15 + (usable ** 1.2) * 0.85

# =============================
# VECTORES POR SENSOR
# =============================
def front_vector_from_angle(angle_deg):
    """
    Front:
    center=45 => Y+
    min=0      => diagonal X-,Y+
    max=90     => diagonal X+,Y+
    """
    # -45..+45 grados relativos
    rel = angle_deg - SERVO_CENTER
    rad = math.radians(rel)

    # base mirando a Y+, así:
    # x = sin(rel)
    # y = cos(rel)
    x = math.sin(rad)
    y = math.cos(rad)

    # normalización ligera
    mag = math.sqrt(x*x + y*y) or 1.0
    return (x / mag, y / mag)

def rear_vector_from_angle(angle_deg):
    """
    Rear:
    center=45 => Y-
    min=0      => diagonal X+,Y-
    max=90     => diagonal X-,Y-
    (invertido respecto a front)
    """
    rel = angle_deg - SERVO_CENTER
    rad = math.radians(rel)

    # invertimos frente/atrás y lateral
    x = -math.sin(rad)
    y = -math.cos(rad)

    mag = math.sqrt(x*x + y*y) or 1.0
    return (x / mag, y / mag)

LEFT_VECTOR = (-1.0, 0.0)
RIGHT_VECTOR = (1.0, 0.0)

# =============================
# LOOP DE ESCANEO DE SERVOS + ULTRASONICS
# solo front y rear se mueven
# left/right son fijos
# =============================
def ultrasonic_loop():
    global distances_state

    # patrones distintos para que no se vean sincronizados mecánicos
    front_pattern = [20, 35, 45, 60, 70, 55, 45, 30]
    rear_pattern  = [65, 50, 45, 35, 20, 30, 45, 60]

    idx = 0

    while True:
        if not touch_active:
            servo.set_angle(FRONT_SERVO_CHANNEL, SERVO_CENTER)
            servo.set_angle(REAR_SERVO_CHANNEL, SERVO_CENTER)
            servo_angles["front"] = SERVO_CENTER
            servo_angles["rear"] = SERVO_CENTER
            time.sleep(0.08)
            continue

        # mover front
        fa = front_pattern[idx % len(front_pattern)]
        servo.set_angle(FRONT_SERVO_CHANNEL, fa)
        servo_angles["front"] = fa
        time.sleep(0.025)

        # leer front
        distances_state["front"] = ultrasonics["front"].get_distance()

        # leer left fijo
        distances_state["left"] = ultrasonics["left"].get_distance()

        # mover rear
        ra = rear_pattern[idx % len(rear_pattern)]
        servo.set_angle(REAR_SERVO_CHANNEL, ra)
        servo_angles["rear"] = ra
        time.sleep(0.025)

        # leer rear
        distances_state["rear"] = ultrasonics["rear"].get_distance()

        # leer right fijo
        distances_state["right"] = ultrasonics["right"].get_distance()

        idx += 1
        time.sleep(0.02)

threading.Thread(target=ultrasonic_loop, daemon=True).start()

# =============================
# CÁLCULO DEL VECTOR DE ESPACIO LIBRE
# =============================
def compute_space_vector(pin):
    """
    Combina los 4 sensores en un vector XY continuo.
    - left/right fijos
    - front/rear según ángulo de sus servos
    - si un sensor no tiene lectura, se descarta
    """
    behavior = TOUCH_BEHAVIOR[pin]

    total_x = 0.0
    total_y = 0.0
    used = 0

    # FRONT
    d_front = distances_state["front"]
    w_front = distance_to_weight(d_front)
    if w_front is not None:
        vx, vy = front_vector_from_angle(servo_angles["front"])
        total_x += vx * w_front
        total_y += vy * w_front
        used += 1

    # REAR
    d_rear = distances_state["rear"]
    w_rear = distance_to_weight(d_rear)
    if w_rear is not None:
        vx, vy = rear_vector_from_angle(servo_angles["rear"])
        total_x += vx * w_rear
        total_y += vy * w_rear
        used += 1

    # LEFT
    d_left = distances_state["left"]
    w_left = distance_to_weight(d_left)
    if w_left is not None:
        total_x += LEFT_VECTOR[0] * w_left
        total_y += LEFT_VECTOR[1] * w_left
        used += 1

    # RIGHT
    d_right = distances_state["right"]
    w_right = distance_to_weight(d_right)
    if w_right is not None:
        total_x += RIGHT_VECTOR[0] * w_right
        total_y += RIGHT_VECTOR[1] * w_right
        used += 1

    if used == 0:
        return None, None, 0.0

    # un poco de "exploración" según personalidad
    total_x += random.uniform(-0.15, 0.15) * behavior["explore"]
    total_y += random.uniform(-0.15, 0.15) * behavior["explore"]

    mag = math.sqrt(total_x * total_x + total_y * total_y)
    return total_x, total_y, mag

# =============================
# EVALÚA SI EL VECTOR ACTUAL ESTÁ BLOQUEADO
# =============================
def is_vector_blocked(x, y):
    """
    Revisa si el vector apunta principalmente hacia una zona con obstáculo.
    """
    if x is None or y is None:
        return True

    # eje dominante
    if abs(y) >= abs(x):
        # domina Y
        if y >= 0:
            d = distances_state["front"]
        else:
            d = distances_state["rear"]
    else:
        # domina X
        if x >= 0:
            d = distances_state["right"]
        else:
            d = distances_state["left"]

    if d is None:
        return True

    return d <= OBSTACLE_CM

# =============================
# CONVIERTE VECTOR DE ESPACIO A CMD_MOVE
# =============================
def vector_to_move(pin, vx, vy):
    behavior = TOUCH_BEHAVIOR[pin]

    base_speed = behavior["base_speed"]
    jitter = behavior["jitter"]

    mag = math.sqrt(vx * vx + vy * vy)

    # si el vector es muy pequeño, movimiento exploratorio pequeño
    if mag < 0.08:
        x = random.uniform(-base_speed * 0.6, base_speed * 0.6)
        y = random.uniform(-base_speed * 0.6, base_speed * 0.6)
        steps = clamp(behavior["steps"] + random.randint(-1, 1), 1, MAX_STEPS)
        return x, y, steps

    # normalizar
    nx = vx / mag
    ny = vy / mag

    # escala según fuerza del vector
    strength = clamp(mag, 0.2, 1.8)

    speed = base_speed * strength

    x = nx * speed
    y = ny * speed

    # jitter orgánico
    x += random.uniform(-jitter, jitter)
    y += random.uniform(-jitter, jitter)

    # limitar
    x = clamp(x, -MAX_AXIS, MAX_AXIS)
    y = clamp(y, -MAX_AXIS, MAX_AXIS)

    # pasos variables por personalidad
    steps = clamp(behavior["steps"] + random.randint(-2, 2), 1, MAX_STEPS)

    return x, y, steps

# =============================
# LOOP PRINCIPAL
# =============================
touching_pin = None
did_shake = False
last_move_time = 0.0
last_move_vector = (None, None)

try:
    while True:
        # OJO:
        # con PUD_UP, normalmente "presionado" = LOW (False)
        # si en tu sistema te funciona al revés, deja == True
        # Como tu código original usaba True, lo dejo igual.
        active_pins = [p for p in TOUCH_PINS if GPIO.input(p) == True]

        # ---------- TOUCH ON ----------
        if active_pins:
            pin = active_pins[0]

            if touching_pin != pin:
                print(f"🖐 Touch ON {pin} ({TOUCH_BEHAVIOR[pin]['name']})")
                notify_tacto_server(pin)

                touching_pin = pin
                touch_active = True
                did_shake = False
                last_move_vector = (None, None)

            # baile inicial solo una vez por activación
            if not did_shake:
                do_shake_for_touch(pin)
                did_shake = True
                time.sleep(0.08)

            # recalcular movimiento
            need_move = False

            if last_move_vector[0] is None:
                need_move = True
            elif is_vector_blocked(last_move_vector[0], last_move_vector[1]):
                print("🚧 Dirección actual bloqueada, recalculando...")
                need_move = True
            elif time.time() - last_move_time >= RECHECK_INTERVAL:
                need_move = True

            if need_move:
                vx, vy, mag = compute_space_vector(pin)

                print(
                    f"📡 dist front={distances_state['front']}@{servo_angles['front']}° | "
                    f"left={distances_state['left']} | "
                    f"right={distances_state['right']} | "
                    f"rear={distances_state['rear']}@{servo_angles['rear']}°"
                )

                if vx is None:
                    # sin lecturas válidas => exploratorio
                    behavior = TOUCH_BEHAVIOR[pin]
                    x = random.uniform(-behavior["base_speed"], behavior["base_speed"])
                    y = random.uniform(-behavior["base_speed"], behavior["base_speed"])
                    steps = clamp(behavior["steps"], 1, MAX_STEPS)
                    print("📡 Sin lecturas válidas -> exploración")
                    send_move(x, y, steps)
                    last_move_vector = (x, y)
                else:
                    x, y, steps = vector_to_move(pin, vx, vy)
                    print(f"🧭 space_vector=({vx:.2f}, {vy:.2f}) mag={mag:.2f} -> move=({x:.1f}, {y:.1f}) steps={steps}")
                    send_move(x, y, steps)
                    last_move_vector = (x, y)

                last_move_time = time.time()

        # ---------- TOUCH OFF ----------
        else:
            if touching_pin is not None:
                print("✋ Touch OFF → STOP")
                send_stop()

            touching_pin = None
            touch_active = False
            did_shake = False
            last_move_vector = (None, None)

        time.sleep(0.03)

except KeyboardInterrupt:
    print("\nCerrando sistema")

finally:
    tacto_queue.put(None)

    try:
        send_stop()
    except:
        pass

    sock.close()

    for u in ultrasonics.values():
        u.close()

    servo.set_angle(FRONT_SERVO_CHANNEL, SERVO_CENTER)
    servo.set_angle(REAR_SERVO_CHANNEL, SERVO_CENTER)
    time.sleep(0.1)
    servo.relax()

    GPIO.cleanup()
    
