import socket
import time
import random
import requests
import RPi.GPIO as GPIO

# =============================
# CONFIG
# =============================
TOUCH_PINS = [21, 20]        # puedes agregar más
SERVER_IP = "127.0.0.1"
CMD_PORT = 5002
TACTO_SERVER = "http://192.168.0.200:5822/touch"

CMD_STOP = "CMD_MOVE#1#0#0#8#0\n"

CMD_FORWARD_OPTIONS = [
    "CMD_MOVE#1#16#0#8#0\n",
    "CMD_MOVE#1#33#1#8#0\n"
]

# =============================
# GPIO
# =============================
GPIO.setmode(GPIO.BCM)
for pin in TOUCH_PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# =============================
# SOCKET MOVIMIENTO
# =============================
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((SERVER_IP, CMD_PORT))
print("Cliente movimiento conectado")

touching_pin = None
last_auto_move = 0
AUTO_INTERVAL = 1.2

def notify_tacto_server(pin):
    try:
        requests.post(
            TACTO_SERVER,
            json={"pin": pin},
            timeout=0.3
        )
    except Exception as e:
        print("⚠ Tacto server no responde:", e)

try:
    while True:
        now = time.time()

        active_pins = [p for p in TOUCH_PINS if GPIO.input(p) == GPIO.HIGH]

        # =============================
        # TOQUE ACTIVO
        # =============================
        if active_pins:
            pin = active_pins[0]  # prioridad al primero
            if touching_pin != pin:
                print(f" Touch ON pin {pin}")
                notify_tacto_server(pin)

            touching_pin = pin
            cmd = random.choice(CMD_FORWARD_OPTIONS)
            sock.send(cmd.encode())
            time.sleep(0.12)

        # =============================
        # SIN TOQUE
        # =============================
        else:
            if touching_pin is not None:
                print(" Touch OFF → STOP")
                sock.send(CMD_STOP.encode())
                touching_pin = None
                last_auto_move = now

            if now - last_auto_move > AUTO_INTERVAL:
                cmd = random.choice(CMD_FORWARD_OPTIONS)
                sock.send(cmd.encode())
                last_auto_move = now

        time.sleep(0.02)

except KeyboardInterrupt:
    print("\n Cerrando")

finally:
    sock.send(CMD_STOP.encode())
    sock.close()
    GPIO.cleanup()
