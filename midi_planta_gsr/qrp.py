import socket
import time
import qrcode
import threading
import sys

HOST = "192.168.0.1"
PORT = 23

FEED = 500
SCALE_Y = 4.0

SIZE_CM = 8
UNITS_PER_CM = 3.33
SIZE_UNITS = SIZE_CM * UNITS_PER_CM

TEXT_SCALE = 1.2

# =========================================
# PAUSA GLOBAL
# =========================================
paused = False

def teclado_listener():
    global paused

    print("\n[CONTROLES]")
    print("p = pausa/reanudar")
    print("q = salir\n")

    while True:
        tecla = sys.stdin.read(1)

        if tecla == "p":
            paused = not paused

            if paused:
                print("\n[PAUSADO]")
                print("Ajustar el lápiz y presionar 'p' para continuar\n")
            else:
                print("\n[REANUDANDO]\n")

        elif tecla == "q":
            print("\n[SALIENDO]")
            os._exit(0)

def check_pause():
    global paused

    while paused:
        time.sleep(0.1)

# =========================================
# CONEXIÓN
# =========================================
def conectar():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    s.connect((HOST, PORT))
    print("[OK] Conectado")
    return s

def enviar(sock, cmd):
    check_pause()

    sock.sendall((cmd + "\n").encode())

def esperar_ok(sock):
    buffer = ""

    while True:
        check_pause()

        try:
            data = sock.recv(1024).decode(errors="ignore")

            if data:
                buffer += data

                if "ok" in buffer.lower():
                    return

        except socket.timeout:
            continue

def cmd(sock, g):
    print(">>>", g)
    enviar(sock, g)
    esperar_ok(sock)

# =========================================
# MOVIMIENTO
# =========================================
def mover(sock, x, y):
    y *= SCALE_Y
    cmd(sock, f"G1 X{x:.2f} Y{y:.2f} F{FEED}")

def rapido(sock, x, y):
    y *= SCALE_Y
    cmd(sock, f"G0 X{x:.2f} Y{y:.2f}")

# =========================================
# QR
# =========================================
def generar_qr(data):
    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()

def dibujar_cuadro(sock, x, y, s):
    rapido(sock, x, y)

    cmd(sock, "G0 Z-4")

    mover(sock, x+s, y)
    mover(sock, x+s, y+s)
    mover(sock, x, y+s)
    mover(sock, x, y)

    cmd(sock, "G0 Z0")

# =========================================
# LETRAS
# =========================================
def letra_I(sock, x, y, s):
    mover(sock, x, y)
    mover(sock, x, y+s)

def letra_G(sock, x, y, s):
    mover(sock, x+s, y+s)
    mover(sock, x, y+s)
    mover(sock, x, y)
    mover(sock, x+s, y)
    mover(sock, x+s, y+s/2)
    mover(sock, x+s/2, y+s/2)

def letra_E(sock, x, y, s):
    mover(sock, x+s, y+s)
    mover(sock, x, y+s)
    mover(sock, x, y)
    mover(sock, x+s, y)
    mover(sock, x, y+s/2)
    mover(sock, x+s*0.7, y+s/2)

def letra_J(sock, x, y, s):
    mover(sock, x+s, y+s)
    mover(sock, x+s, y)
    mover(sock, x, y)

def letra_O(sock, x, y, s):
    mover(sock, x, y)
    mover(sock, x+s, y)
    mover(sock, x+s, y+s)
    mover(sock, x, y+s)
    mover(sock, x, y)

def letra_R(sock, x, y, s):
    mover(sock, x, y)
    mover(sock, x, y+s)
    mover(sock, x+s, y+s)
    mover(sock, x+s, y+s/2)
    mover(sock, x, y+s/2)
    mover(sock, x+s, y)

def letra_M(sock, x, y, s):
    mover(sock, x, y)
    mover(sock, x, y+s)
    mover(sock, x+s/2, y)
    mover(sock, x+s, y+s)
    mover(sock, x+s, y)

def letra_F(sock, x, y, s):
    mover(sock, x, y)
    mover(sock, x, y+s)
    mover(sock, x+s, y+s)
    mover(sock, x, y+s/2)
    mover(sock, x+s*0.7, y+s/2)

def letra_K(sock, x, y, s):
    mover(sock, x, y)
    mover(sock, x, y+s)
    mover(sock, x+s, y+s)
    mover(sock, x, y+s/2)
    mover(sock, x+s, y)

def dos_puntos(sock, x, y, s):
    mover(sock, x, y+s*0.7)
    mover(sock, x, y+s*0.8)

    mover(sock, x, y+s*0.2)
    mover(sock, x, y+s*0.3)

def arroba(sock, x, y, s):
    mover(sock, x+s, y+s/2)
    mover(sock, x+s/2, y+s)
    mover(sock, x, y+s/2)
    mover(sock, x+s/2, y)

# =========================================
# MAIN
# =========================================
def main():

    # hilo teclado
    t = threading.Thread(target=teclado_listener, daemon=True)
    t.start()

    url = "https://www.instagram.com/jorgemfk"
    matriz = generar_qr(url)

    n = len(matriz)
    cell = SIZE_UNITS / n

    sock = conectar()

    enviar(sock, "$X\n")
    time.sleep(0.5)

    cmd(sock, "G21")
    cmd(sock, "G90")
    cmd(sock, "G92 X0 Y0")

    cmd(sock, "G0 Z0")

    # =====================================
    # DIBUJAR QR
    # =====================================
    for i in range(n):
        for j in range(n):

            check_pause()

            if matriz[i][j]:

                x = j * cell
                y = (n - i) * cell

                dibujar_cuadro(sock, x, y, cell)

    # =====================================
    # TEXTO
    # =====================================
    base_y = -5

    x = 0
    s = TEXT_SCALE

    texto = [
        letra_I,
        letra_G,
        dos_puntos,
        arroba,
        letra_J,
        letra_O,
        letra_R,
        letra_G,
        letra_E,
        letra_M,
        letra_F,
        letra_K
    ]

    for letra in texto:

        check_pause()

        rapido(sock, x, base_y)

        cmd(sock, "G0 Z-4")

        letra(sock, x, base_y, s)

        cmd(sock, "G0 Z0")

        x += s * 1.7

    cmd(sock, "G0 Z0")

    sock.close()

    print("[FIN]")

# =========================================
# ENTRY POINT
# =========================================
if __name__ == "__main__":
    main()
