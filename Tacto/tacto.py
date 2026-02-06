# coding:utf-8
import socket
import time
import threading
import queue
import requests
import RPi.GPIO as GPIO
from pca9685 import PCA9685

# =============================
# CONFIG
# =============================
SERVER_IP = "127.0.0.1"
CMD_PORT = 5002

# Touch
TOUCH_PINS = [21]
TACTO_SERVER = "http://192.168.11.82:5822/touch"

# Sonar
TRIGGER_PIN = 27
ECHO_PIN = 22
OBSTACLE_CM = 25.0

# Servo
SERVO_CHANNEL = 1
SERVO_CENTER = 45

# Movimiento
CMD_FORWARD = "CMD_MOVE#1#16#0#8#0\n"
CMD_TURN = "CMD_MOVE#1#33#1#8#0\n"
CMD_STOP = "CMD_MOVE#1#0#0#8#0\n"

# =============================
# GPIO SETUP
# =============================
GPIO.setmode(GPIO.BCM)

# Touch
for pin in TOUCH_PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Sonar
GPIO.setup(TRIGGER_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)
GPIO.output(TRIGGER_PIN, False)
time.sleep(0.1)

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

    def set_servo_angle(self, channel, angle):
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
# SONAR
# =============================
def read_distance_cm():
    GPIO.output(TRIGGER_PIN, True)
    time.sleep(0.00001)
    GPIO.output(TRIGGER_PIN, False)

    timeout = time.time() + 0.04

    while GPIO.input(ECHO_PIN) == 0:
        if time.time() > timeout:
            return None
        start = time.time()

    while GPIO.input(ECHO_PIN) == 1:
        if time.time() > timeout:
            return None
        end = time.time()

    duration = end - start
    return round(duration * 17150, 2)

# =============================
# TACTO ASYNC WORKER
# =============================
tacto_queue = queue.Queue()

def tacto_worker():
    while True:
        pin = tacto_queue.get()
        if pin is None:
            break
        try:
            requests.post(
                TACTO_SERVER,
                json={"pin": pin},
                timeout=0.3
            )
        except Exception as e:
            print("⚠ tacto server:", e)
        tacto_queue.task_done()

threading.Thread(target=tacto_worker, daemon=True).start()

def notify_tacto_server(pin):
    tacto_queue.put(pin)

# =============================
# SONAR SCAN THREAD
# Solo escanea si touch activo
# =============================
sonar_state = {
    "angle": SERVO_CENTER,
    "distance": None
}

touch_active = False

def sonar_scan_loop():

    angles = list(range(0, 91, 15)) + list(range(90, -1, -15))

    while True:

        if not touch_active:
            servo.set_servo_angle(SERVO_CHANNEL, SERVO_CENTER)
            time.sleep(0.1)
            continue

        for angle in angles:

            if not touch_active:
                break

            servo.set_servo_angle(SERVO_CHANNEL, angle)
            time.sleep(0.03)

            dist = read_distance_cm()
            sonar_state["angle"] = angle
            sonar_state["distance"] = dist

threading.Thread(target=sonar_scan_loop, daemon=True).start()

# =============================
# SOCKET MOVIMIENTO
# =============================
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((SERVER_IP, CMD_PORT))
print("Cliente movimiento conectado")

touching_pin = None
current_direction = "forward"

# =============================
# LOOP PRINCIPAL
# =============================
try:
    while True:

        active_pins = [p for p in TOUCH_PINS if GPIO.input(p)== True]

        # =============================
        # TOUCH ACTIVO
        # =============================
        if active_pins:

            pin = active_pins[0]

            if touching_pin != pin:
                print(f"🖐 Touch ON {pin}")
                notify_tacto_server(pin)

            touching_pin = pin
            touch_active = True

            dist = sonar_state["distance"]
            angle = sonar_state["angle"]

            if dist is not None:
                print(f"📡 {dist} cm @ {angle}°")

                if dist <= OBSTACLE_CM:
                    if angle < 45:
                        if current_direction != "turn":
                            sock.send(CMD_TURN.encode())
                            current_direction = "turn"
                    else:
                        if current_direction != "forward":
                            sock.send(CMD_FORWARD.encode())
                            current_direction = "forward"
                else:
                    if current_direction != "forward":
                        sock.send(CMD_FORWARD.encode())
                        current_direction = "forward"

        # =============================
        # TOUCH OFF
        # =============================
        else:
            if touching_pin is not None:
                print("✋ Touch OFF → STOP")

                sock.send(CMD_STOP.encode())
                touching_pin = None
                current_direction = "forward"

            touch_active = False

        time.sleep(0.03)

except KeyboardInterrupt:
    print("\nCerrando sistema")

finally:
    tacto_queue.put(None)
    sock.send(CMD_STOP.encode())
    sock.close()
    servo.relax()
    GPIO.cleanup()
