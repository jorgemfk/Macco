import socket
import time
import random
import RPi.GPIO as GPIO

TOUCH_PIN = 21
SERVER_IP = "127.0.0.1"
SERVER_PORT = 5002

CMD_RIGHT = "CMD_MOVE#1#34#1#8#0\n"
CMD_STOP  = "CMD_MOVE#1#0#0#8#0\n"

CMD_FORWARD_OPTIONS = [
    "CMD_MOVE#1#16#0#8#0\n",   # frente
    "CMD_MOVE#1#33#1#8#0\n"    # frente-derecha suave
]

GPIO.setmode(GPIO.BCM)
GPIO.setup(TOUCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((SERVER_IP, SERVER_PORT))
print(" Cliente touch conectado")

touching = False
last_auto_move = 0
AUTO_INTERVAL = 1.2   # segundos entre movimientos automáticos

try:
    while True:
        touch_state = GPIO.input(TOUCH_PIN)
        now = time.time()

        # =========================
        # TOCANDO → DERECHA
        # =========================
        if touch_state == True:
            if not touching:
                print(" Touch ON → MOV")
            touching = True
            cmd = random.choice(CMD_FORWARD_OPTIONS)
            print(" AUTO:", cmd.strip())
            sock.send(cmd.encode())
            time.sleep(0.12)

        # =========================
        # SOLTÓ → STOP + AUTO
        # =========================
        else:
            if touching:
                print(" Touch OFF → STOP")
                sock.send(CMD_STOP.encode())
                touching = False
                last_auto_move = now


        time.sleep(0.02)

except KeyboardInterrupt:
    print("\n Cerrando")

finally:
    sock.send(CMD_STOP.encode())
    sock.close()
    GPIO.cleanup()
