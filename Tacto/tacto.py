# -*- coding: utf-8 -*-
import socket
import time
import RPi.GPIO as GPIO

# =============================
# CONFIGURACIÓN
# =============================
TOUCH_PIN = 21
SERVER_IP = "127.0.0.1"
SERVER_PORT = 5002
DEBOUNCE_TIME = 0.5  # segundos

# Secuencia de movimientos a enviar
MOVE_SEQUENCE = [
    "CMD_MOVE#1#-1#16#8#0\n",
    "CMD_MOVE#1#-1#17#8#0\n",
    "CMD_MOVE#1#-1#18#8#0\n",
]

# =============================
# GPIO SETUP
# =============================
GPIO.setmode(GPIO.BCM)
GPIO.setup(TOUCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# =============================
# TCP CLIENT
# =============================
def connect_client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, SERVER_PORT))
    print(" Conectado a", SERVER_IP, SERVER_PORT)
    return sock

# =============================
# MAIN
# =============================
def main():
    sock = connect_client()
    last_touch_time = 0
    touching = False

    try:
        while True:
            touch_state = GPIO.input(TOUCH_PIN)

            # TOUCH DETECTADO
            if touch_state == GPIO.LOW and not touching:
                now = time.time()
                if now - last_touch_time > DEBOUNCE_TIME:
                    touching = True
                    last_touch_time = now

                    print(" Touch detectado → enviando movimientos")

                    for cmd in MOVE_SEQUENCE:
                        print("->", cmd.strip())
                        sock.send(cmd.encode("utf-8"))
                        time.sleep(0.08)

            # TOUCH LIBERADO
            elif touch_state == GPIO.HIGH:
                touching = False

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n Cerrando")
    finally:
        sock.close()
        GPIO.cleanup()

# =============================
if __name__ == "__main__":
    main()
