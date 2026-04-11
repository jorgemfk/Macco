# coding:utf-8
import socket
import time
import threading
import queue
import requests
import math
import random

import RPi.GPIO as GPIO
from pca9685 import PCA9685

# =============================
# CONFIG
# =============================
SERVER_IP = "127.0.0.1"
CMD_PORT = 5002

# Touch
TOUCH_PINS = [21,20]  # puedes volver a agregar 25,20,12 si quieres
TACTO_SERVER = "http://192.168.0.82:5822/touch"

# Ultrasonicos (SOLO FRONT Y REAR)
ULTRASONICS = [
    {"trigger": 27, "echo": 22, "name": "front"},  # servo canal 1
    {"trigger": 5,  "echo": 6,  "name": "rear"},   # servo canal 2
    {"trigger": 13, "echo": 19, "name": "left"},
    {"trigger": 26, "echo": 16, "name": "right"},
]

MAX_DISTANCE_CM = 300.0
OBSTACLE_CM = 25.0
RECHECK_INTERVAL = 0.12    # evita saturar server / recalcular demasiado rápido

# =============================
# SERVOS DE ULTRASONIC
# front = canal 1 (pwm_41)
# rear  = canal 2 (pwm_41)
# =============================
FRONT_SERVO_CHANNEL = 1
REAR_SERVO_CHANNEL = 2

SERVO_CENTER = 45
SERVO_MIN = 0
SERVO_MAX = 90

# Patrones de barrido
FRONT_PATTERN = [20, 35, 45, 60, 70, 55, 45, 30]
REAR_PATTERN  = [65, 50, 45, 35, 20, 30, 45, 60]

# mover -> pausa -> leer -> pausa -> leer
SERVO_SETTLE_TIME = 0.06
READ_BETWEEN_SAMPLES = 0.06
POST_READ_PAUSE = 0.04
SENSOR_INTERLEAVE_PAUSE = 0.06

# =============================
# LÍMITES MOVIMIENTO ROBOT
# =============================
MAX_AXIS = 25
MAX_STEPS = 10

# =============================
# PERSONALIDAD POR TOUCH PIN
# AQUI agregué duración de sesión por touch
# =============================
TOUCH_BEHAVIOR = {
    21: {
        "name": "curioso",
        "base_speed": 13,
        "steps": 6,
        "jitter": 2,
        "explore": 1.0,
        "session_min": 3.0,
        "session_max": 4.5,
        "shake": ['CMD_POSITION#8#3#0', 'CMD_POSITION#8#2#0', 
        'CMD_POSITION#8#1#0', 'CMD_POSITION#8#0#0', 'CMD_POSITION#8#-1#0', 
        'CMD_POSITION#8#-2#0', 'CMD_POSITION#8#-4#0', 'CMD_POSITION#7#-5#0', 
        'CMD_POSITION#6#-6#0', 'CMD_POSITION#6#-7#0', 'CMD_POSITION#5#-8#0', 
        'CMD_POSITION#4#-8#0', 'CMD_POSITION#3#-8#0', 'CMD_POSITION#2#-9#0', 
        'CMD_POSITION#1#-9#0', 'CMD_POSITION#0#-9#0', 'CMD_POSITION#-2#-9#0', 
        'CMD_POSITION#-3#-9#0', 'CMD_POSITION#-4#-9#0', 'CMD_POSITION#-6#-9#0',
         'CMD_POSITION#-7#-9#0', 'CMD_POSITION#-8#-8#0', 'CMD_POSITION#-9#-8#0',
          'CMD_POSITION#-9#-7#0', 'CMD_POSITION#-10#-6#0', 'CMD_POSITION#-10#-5#0',
           'CMD_POSITION#-10#-4#0', 'CMD_POSITION#-11#-4#0', 'CMD_POSITION#-11#-3#0', 
           'CMD_POSITION#-11#-2#0', 'CMD_POSITION#-11#-1#0', 'CMD_POSITION#-11#0#0', 
           'CMD_POSITION#-10#0#0', 'CMD_POSITION#-9#1#0', 'CMD_POSITION#-8#1#0', 
           'CMD_POSITION#-7#1#0', 'CMD_POSITION#-6#2#0', 'CMD_POSITION#-5#2#0', 
           'CMD_POSITION#-5#1#0', 'CMD_POSITION#-4#1#0', 'CMD_POSITION#-4#0#0', 
           'CMD_POSITION#-3#0#0', 'CMD_POSITION#-2#0#0', 'CMD_POSITION#-2#-1#0', 
           'CMD_POSITION#-2#-2#0', 'CMD_POSITION#-2#-3#0', 'CMD_POSITION#-2#-4#0',
            'CMD_POSITION#-2#-5#0', 'CMD_POSITION#-2#-6#0', 'CMD_POSITION#-3#-6#0',
             'CMD_POSITION#-4#-6#0', 'CMD_POSITION#-5#-6#0', 'CMD_POSITION#-6#-6#0',
            'CMD_POSITION#0#0#0',
        ],
    },
    25: {
        "name": "nervioso",
        "base_speed": 11,
        "steps": 9,
        "jitter": 4,
        "explore": 1.4,
        "session_min": 4.0,
        "session_max": 6.0,
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
        "session_min": 3.0,
        "session_max": 4.0,
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
        "session_min": 4.0,
        "session_max": 6.0,
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
GPIO.setwarnings(False)

# Touch
for pin in TOUCH_PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Ultrasonic GPIO
for cfg in ULTRASONICS:
    GPIO.setup(cfg["trigger"], GPIO.OUT)
    GPIO.setup(cfg["echo"], GPIO.IN)
    GPIO.output(cfg["trigger"], False)

time.sleep(0.8)

# =============================
# SERVO PCA9685
# =============================
def map_value(value, from_low, from_high, to_low, to_high):
    """Map a value from one range to another."""
    return (to_high - to_low) * (value - from_low) / (from_high - from_low) + to_low

class Servo:
    def __init__(self):
        self.pwm_40 = PCA9685(0x40, debug=True)
        self.pwm_41 = PCA9685(0x41, debug=True)
        # Set the cycle frequency of PWM to 50 Hz
        self.pwm_40.set_pwm_freq(50)
        time.sleep(0.01)
        self.pwm_41.set_pwm_freq(50)
        time.sleep(0.01)

    def set_angle(self, channel, angle):
        """
        Convert the input angle to the value of PCA9685 and set the servo angle.
        
        :param channel: Servo channel (0-31)
        :param angle: Angle in degrees (0-180)
        """
        if channel < 16:
            duty_cycle = map_value(angle, 0, 180, 500, 2500)
            duty_cycle = map_value(duty_cycle, 0, 20000, 0, 4095)
            self.pwm_41.set_pwm(channel, 0, int(duty_cycle))
        elif channel >= 16 and channel < 32:
            channel -= 16
            duty_cycle = map_value(angle, 0, 180, 500, 2500)
            duty_cycle = map_value(duty_cycle, 0, 20000, 0, 4095)
            self.pwm_40.set_pwm(channel, 0, int(duty_cycle))

    def relax(self):
        """Relax all servos by setting their PWM values to 4096."""
        for i in range(8):
            self.pwm_41.set_pwm(i + 8, 4096, 4096)
            self.pwm_40.set_pwm(i, 4096, 4096)
            self.pwm_40.set_pwm(i + 8, 4096, 4096)

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
            # conserva info touch al otro server
            requests.post(TACTO_SERVER, json={"pin": pin}, timeout=0.3)
        except Exception as e:
            print("⚠ tacto server:", e)
        tacto_queue.task_done()

threading.Thread(target=tacto_worker, daemon=True).start()

def notify_tacto_server(pin):
    tacto_queue.put(pin)

# =============================
# ESTADO GLOBAL DE ULTRASONIC
# =============================
distances_state = {
    "front": None,
    "rear": None,
    "left": None,
    "right": None,
}

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
    print("POS", cmd)

def do_shake_for_touch(pin):
    """
    Conserva los movimientos de cadera iniciales antes de moverte.
    """
    behavior = TOUCH_BEHAVIOR.get(pin)
    if not behavior:
        return
    for cmd in behavior["shake"]:
        send_cmd(cmd)
        time.sleep(0.03)

# =============================
# ULTRASONIC MANUAL (ESTABLE)
# =============================
def measure_distance(trigger_pin, echo_pin, timeout=0.03):
    """
    Retorna distancia en cm o None.
    """
    GPIO.output(trigger_pin, False)
    time.sleep(0.0002)

    GPIO.output(trigger_pin, True)
    time.sleep(0.00001)
    GPIO.output(trigger_pin, False)

    start_wait = time.time()
    pulse_start = None
    pulse_end = None

    # esperar subida
    while GPIO.input(echo_pin) == 0:
        pulse_start = time.time()
        if pulse_start - start_wait > timeout:
            return None

    # esperar bajada
    while GPIO.input(echo_pin) == 1:
        pulse_end = time.time()
        if pulse_end - pulse_start > timeout:
            return None

    if pulse_start is None or pulse_end is None:
        return None

    pulse_duration = pulse_end - pulse_start
    distance = (pulse_duration * 34300) / 2.0

    if distance < 2 or distance > MAX_DISTANCE_CM:
        return None

    return round(distance, 1)

def get_sensor_cfg(name):
    for cfg in ULTRASONICS:
        if cfg["name"] == name:
            return cfg
    return None

# =============================
# CONVERSIÓN DE DISTANCIA A PESO
# más distancia = más "atracción" hacia esa dirección
# =============================
def distance_to_weight(d):
    if d is None or d <= 0:
        return None

    if d <= OBSTACLE_CM:
        return 0.05

    usable = clamp((d - OBSTACLE_CM) / 120.0, 0.0, 1.0)
    return 0.15 + (usable ** 1.2) * 0.85

# =============================
# VECTORES POR SENSOR
# =============================
LEFT_VECTOR = (-1.0, 0.0)
RIGHT_VECTOR = (1.0, 0.0)
def front_vector_from_angle(angle_deg):
    """
    Front:
    center=45 => Y+
    min=0      => diagonal X-,Y+
    max=90     => diagonal X+,Y+
    """
    rel = angle_deg - SERVO_CENTER
    rad = math.radians(rel)

    x = math.sin(rad)
    y = math.cos(rad)

    mag = math.sqrt(x*x + y*y) or 1.0
    return (x / mag, y / mag)

def rear_vector_from_angle(angle_deg):
    """
    Rear:
    center=45 => Y-
    min=0      => diagonal X+,Y-
    max=90     => diagonal X-,Y-
    """
    rel = angle_deg - SERVO_CENTER
    rad = math.radians(rel)

    x = -math.sin(rad)
    y = -math.cos(rad)

    mag = math.sqrt(x*x + y*y) or 1.0
    return (x / mag, y / mag)


def choose_best_direction():
    """
    Elige la dirección con mayor distancia medible.
    Retorna: (vx, vy, label, dist)
    """
    candidates = []

    if distances_state["front"] is not None:
        candidates.append(("front", distances_state["front"], 0, 1))

    if distances_state["rear"] is not None:
        candidates.append(("rear", distances_state["rear"], 0, -1))

    if distances_state.get("left") is not None:
        candidates.append(("left", distances_state["left"], -1, 0))

    if distances_state.get("right") is not None:
        candidates.append(("right", distances_state["right"], 1, 0))

    if not candidates:
        return None, None, None, None

    # elegir mayor distancia
    best = max(candidates, key=lambda x: x[1])

    label, dist, vx, vy = best
    return vx, vy, label, dist

# =============================
# SCANEO FRONT / REAR
# mueve servo -> pausa -> lee -> pausa -> lee
# =============================
def scan_sensor(name, angle):
    cfg = get_sensor_cfg(name)
    if not cfg:
        return None

    if name == "front":
        ch = FRONT_SERVO_CHANNEL
    else:
        ch = REAR_SERVO_CHANNEL

    # mover servo
    servo.set_angle(ch, angle)
    servo_angles[name] = angle

    # pausa mecánica
    time.sleep(SERVO_SETTLE_TIME)

    # leer 1
    d1 = measure_distance(cfg["trigger"], cfg["echo"])

    # pausa
    time.sleep(POST_READ_PAUSE)

    # leer 2
    d2 = measure_distance(cfg["trigger"], cfg["echo"])

    vals = [v for v in [d1, d2] if v is not None]

    if not vals:
        dist = None
    else:
        vals.sort()
        dist = vals[len(vals) // 2]

    distances_state[name] = dist
    return dist

# =============================
# LOOP DE ESCANEO DE SERVOS + ULTRASONICS
# SOLO FRONT Y REAR
# =============================
def ultrasonic_loop():
    idx = 0

    while True:
        if not touch_active:
            # reposo
            if servo_angles["front"] != SERVO_CENTER:
                servo.set_angle(FRONT_SERVO_CHANNEL, SERVO_CENTER)
                servo_angles["front"] = SERVO_CENTER

            if servo_angles["rear"] != SERVO_CENTER:
                servo.set_angle(REAR_SERVO_CHANNEL, SERVO_CENTER)
                servo_angles["rear"] = SERVO_CENTER

            time.sleep(0.10)
            continue

        # ---------- FRONT ----------
        fa = FRONT_PATTERN[idx % len(FRONT_PATTERN)]
        d_front = scan_sensor("front", fa)

        time.sleep(SENSOR_INTERLEAVE_PAUSE)

        # ---------- REAR ----------
        ra = REAR_PATTERN[idx % len(REAR_PATTERN)]
        d_rear = scan_sensor("rear", ra)

        time.sleep(SENSOR_INTERLEAVE_PAUSE)

        # ---------- LEFT (fijo) ----------
        cfg_l = get_sensor_cfg("left")
        if cfg_l:
            d_left = measure_distance(cfg_l["trigger"], cfg_l["echo"])
            distances_state["left"] = d_left
        else:
            d_left = None

        time.sleep(SENSOR_INTERLEAVE_PAUSE)

        # ---------- RIGHT (fijo) ----------
        cfg_r = get_sensor_cfg("right")
        if cfg_r:
            d_right = measure_distance(cfg_r["trigger"], cfg_r["echo"])
            distances_state["right"] = d_right
        else:
            d_right = None

        idx += 1

        print(
            f"📡 F:{d_front}@{servo_angles['front']}° | "
            f"R:{d_rear}@{servo_angles['rear']}° | "
            f"L:{d_left} | X:{d_right}"
        )

        time.sleep(0.02)

threading.Thread(target=ultrasonic_loop, daemon=True).start()

# =============================
# CÁLCULO DEL VECTOR DE ESPACIO LIBRE
# SOLO FRONT + REAR
# =============================
def compute_space_vector(pin):
    behavior = TOUCH_BEHAVIOR[pin]

    total_x = 0.0
    total_y = 0.0
    used = 0

    # ---------- FRONT ----------
    d = distances_state["front"]
    w = distance_to_weight(d)
    if w is not None:
        vx, vy = front_vector_from_angle(servo_angles["front"])
        total_x += vx * w
        total_y += vy * w
        used += 1

    # ---------- REAR ----------
    d = distances_state["rear"]
    w = distance_to_weight(d)
    if w is not None:
        vx, vy = rear_vector_from_angle(servo_angles["rear"])
        total_x += vx * w
        total_y += vy * w
        used += 1

    # ---------- LEFT ----------
    d = distances_state["left"]
    w = distance_to_weight(d)
    if w is not None:
        total_x += LEFT_VECTOR[0] * w
        total_y += LEFT_VECTOR[1] * w
        used += 1

    # ---------- RIGHT ----------
    d = distances_state["right"]
    w = distance_to_weight(d)
    if w is not None:
        total_x += RIGHT_VECTOR[0] * w
        total_y += RIGHT_VECTOR[1] * w
        used += 1

    if used == 0:
        return None, None, 0.0

    # exploración
    total_x += random.uniform(-0.15, 0.15) * behavior["explore"]
    total_y += random.uniform(-0.15, 0.15) * behavior["explore"]

    mag = math.sqrt(total_x * total_x + total_y * total_y)
    return total_x, total_y, mag
# =============================
# EVALÚA SI EL VECTOR ACTUAL ESTÁ BLOQUEADO
# SOLO FRONT / REAR (por signo de Y)
# =============================
def is_vector_blocked(x, y):
    if x is None or y is None:
        return True

    if abs(y) >= abs(x):
        # eje Y domina
        if y >= 0:
            d = distances_state["front"]
        else:
            d = distances_state["rear"]
    else:
        # eje X domina
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
def apply_minimum(val, min_val=13):
    """Aplica valor mínimo preservando el signo, respeta el 0."""
    if val == 0:
        return 0
    sign = 1 if val > 0 else -1
    return sign * max(abs(val), min_val)

def vector_to_move(pin, vx, vy):
    behavior = TOUCH_BEHAVIOR[pin]
    base_speed = behavior["base_speed"]
    jitter = behavior["jitter"]

    mag = math.sqrt(vx * vx + vy * vy)

    # normalizar
    nx = vx / (mag or 1.0)
    ny = vy / (mag or 1.0)

    strength = clamp(mag, 0.2, 1.8)
    speed = base_speed * strength

    x = nx * speed
    y = ny * speed

    # 🔥 CLAVE: detectar ejes activos reales
    x_active = abs(vx) > 0.01
    y_active = abs(vy) > 0.01

    # aplicar jitter SOLO en ejes activos
    if x_active:
        x += random.uniform(-jitter, jitter)
    else:
        x = 0

    if y_active:
        y += random.uniform(-jitter, jitter)
    else:
        y = 0

    x = clamp(x, -MAX_AXIS, MAX_AXIS)
    y = clamp(y, -MAX_AXIS, MAX_AXIS)

    # aplicar mínimo SOLO en ejes activos
    if x_active:
        x = apply_minimum(x)
    if y_active:
        y = apply_minimum(y)

    steps = clamp(behavior["steps"] + random.randint(-2, 2), 1, MAX_STEPS)

    return x, y, steps
# =============================
# LECTURA DE TOUCH
# IMPORTANTE:
# tu hardware parece estar "activo = True"
# por eso lo dejo así, igual que tu código original
# =============================
def is_touch_stable(pin, checks=4, delay=0.01):
    """
    HIGH estable = touch real
    """
    for _ in range(checks):
        if GPIO.input(pin) != True:
            return False
        time.sleep(delay)
    return True

def is_release_stable(pin, checks=4, delay=0.01):
    """
    LOW estable = touch realmente liberado
    """
    for _ in range(checks):
        if GPIO.input(pin) == True:
            return False
        time.sleep(delay)
    return True

def get_active_touch_pin():
    """
    Devuelve el primer pin con touch real y estable.
    """
    for p in TOUCH_PINS:
        if GPIO.input(p) == True:
            if is_touch_stable(p, checks=4, delay=0.01):
                return p
    return None

# =============================
# SESIÓN DE EXPLORACIÓN POR TOUCH
# Un touch => una sola sesión (3-6 s)
# NO se re-dispara mientras sigue tocado
# Sigue leyendo ultrasonic por hilo paralelo
# =============================
def run_touch_session(pin):
    global touch_active

    behavior = TOUCH_BEHAVIOR[pin]
    session_duration = random.uniform(
        behavior.get("session_min", 3.0),
        behavior.get("session_max", 6.0)
    )

    print(f" Touch ON {pin} ({behavior['name']}) | sesión {session_duration:.2f}s")
    notify_tacto_server(pin)

    # activar escaneo ultrasonic
    touch_active = True

    # cadera inicial antes de moverse
    do_shake_for_touch(pin)
    time.sleep(0.08)
    # =============================
    # DECISIÓN INICIAL (MAYOR DISTANCIA)
    # =============================
    vx, vy, label, dist = choose_best_direction()

    last_move_vector = (None, None)
    last_move_time = 0.0

    if vx is not None:
        print(
            f" F:{distances_state.get('front')} | "
            f"R:{distances_state.get('rear')} | "
            f"L:{distances_state.get('left')} | "
            f"X:{distances_state.get('right')}"
        )

        print(f" DECISIÓN INICIAL → {label.upper()} | distancia={dist} cm")

        x, y, steps = vector_to_move(pin, vx, vy)

        print(
            f" PRIMER MOVIMIENTO → dir={label} "
            f"vec=({vx},{vy}) -> move=({x:.1f},{y:.1f}) steps={steps}"
        )

        send_move(x, y)

        last_move_vector = (x, y)
        last_move_time = time.time()


        time.sleep(0.15)

    else:
        print("⚠ Sin datos iniciales de distancia, entrando en modo exploración")

    session_start = time.time()
    last_move_time = 0.0
    last_move_vector = (None, None)

    # Mantener sesión aunque el dedo siga o ya no siga:
    # la idea es cumplir su exploración completa
    while (time.time() - session_start) < session_duration:
        need_move = False

        if last_move_vector[0] is None:
            need_move = True
        elif is_vector_blocked(last_move_vector[0], last_move_vector[1]):
            print(" Dirección actual bloqueada, recalculando...")
            need_move = True
        elif time.time() - last_move_time >= RECHECK_INTERVAL:
            need_move = True

        if need_move:
            vx, vy, mag = compute_space_vector(pin)

            print(
                f" dist front={distances_state['front']}@{servo_angles['front']}° | "
                f"rear={distances_state['rear']}@{servo_angles['rear']}°"
            )

            if vx is None:
                # sin lecturas válidas => exploratorio
                x = random.uniform(-behavior["base_speed"], behavior["base_speed"])
                y = random.uniform(-behavior["base_speed"], behavior["base_speed"])
                steps = clamp(behavior["steps"], 1, MAX_STEPS)
                print(" Sin lecturas válidas -> exploración")
                send_move(x, y)
                last_move_vector = (x, y)
            else:
                x, y, steps = vector_to_move(pin, vx, vy)
                print(
                    f" space_vector=({vx:.2f}, {vy:.2f}) "
                    f"mag={mag:.2f} -> move=({x:.1f}, {y:.1f}) steps={steps}"
                )
                send_move(x, y)
                last_move_vector = (x, y)

            last_move_time = time.time()

        # pequeño sleep para no saturar CPU
        time.sleep(0.03)

    print("⏹ Fin de sesión touch -> STOP")
    send_stop()

    # desactivar escaneo activo (servos volverán al centro por el hilo)
    touch_active = False

# =============================
# LOOP PRINCIPAL
# Evita re-disparos:
# - solo inicia sesión en flanco de activación
# - luego espera liberación del touch antes de permitir otro
# =============================
touch_latched = False  # True = ya se disparó una sesión y aún no se ha soltado
servo.set_angle(0, 0)
try:
    while True:
        active_pin = get_active_touch_pin()

        # ---------- NUEVO TOUCH (solo si no está latched) ----------
        if active_pin is not None and not touch_latched:
            touch_latched = True

            # Ejecuta una sola sesión completa
            run_touch_session(active_pin)

            # después de la sesión, NO permitir otro touch hasta soltar el sensor
            print(" Esperando liberación del touch para permitir nuevo disparo...")

        # ---------- LIBERACIÓN ----------
        elif touch_latched:
            # no liberes por una sola lectura falsa
            # espera a que TODOS los touch pins estén realmente en release estable
            released = True

            for p in TOUCH_PINS:
                if not is_release_stable(p, checks=4, delay=0.01):
                    released = False
                    break

            if released:
                touch_latched = False
                print(" Touch liberado, listo para siguiente sesión")

        time.sleep(0.03)

except KeyboardInterrupt:
    print("\nCerrando sistema")

finally:
    tacto_queue.put(None)

    try:
        send_stop()
    except:
        pass

    try:
        sock.close()
    except:
        pass

    # regresar servos al centro
    try:
        servo.set_angle(FRONT_SERVO_CHANNEL, SERVO_CENTER)
        servo.set_angle(REAR_SERVO_CHANNEL, SERVO_CENTER)
        time.sleep(0.1)
        servo.relax()
    except:
        pass

    GPIO.cleanup()
