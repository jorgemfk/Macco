import image, lcd, time, audio, math, ubinascii, ujson, socket, os
from Maix import I2S, GPIO
from fpioa_manager import fm
import network
import ustruct

# ========== CONFIGURACIÓN ==========
SSID = "INFINITUM47A4_2.4"
PASW = "eFwN3s9VPP"
SERVER_IP = "192.168.1.207"   # IP de tu Raspberry Pi
SERVER_PORT = 5821

SAMPLE_RATE = 16000
RECORD_TIME = 4
SAMPLE_POINTS = 2048
WAV_CH = 2
SOUND_THRESHOLD = 80  # Ajusta según tu entorno

# ==== LCD ====
lcd.init()
lcd.clear(lcd.WHITE)
lcd.draw_string(10, 10, "Inicializando...", lcd.BLACK, lcd.WHITE)

# ==== AUDIO ====
fm.register(20, fm.fpioa.I2S0_IN_D0, force=True)
fm.register(19, fm.fpioa.I2S0_WS, force=True)
fm.register(18, fm.fpioa.I2S0_SCLK, force=True)
rx = I2S(I2S.DEVICE_0)
rx.channel_config(rx.CHANNEL_0, rx.RECEIVER, align_mode=I2S.STANDARD_MODE)
rx.set_sample_rate(SAMPLE_RATE)

# ==== WIFI ====
class wifi():
    nic = None
    def reset():
        fm.register(25, fm.fpioa.GPIOHS10)
        fm.register(8, fm.fpioa.GPIOHS11)
        fm.register(9, fm.fpioa.GPIOHS12)
        fm.register(28, fm.fpioa.SPI1_D0)
        fm.register(26, fm.fpioa.SPI1_D1)
        fm.register(27, fm.fpioa.SPI1_SCLK)
        wifi.nic = network.ESP32_SPI(
            cs=fm.fpioa.GPIOHS10,
            rst=fm.fpioa.GPIOHS11,
            rdy=fm.fpioa.GPIOHS12,
            spi=1
        )

    def connect(ssid, pasw, max_retries=10):
        wifi.nic.connect(ssid, pasw)
        for i in range(max_retries * 2):  # más intentos y más lentos
            if wifi.nic.isconnected():
                return True
            time.sleep_ms(1000)
            print("Intento WiFi:", i + 1)
        return False

# ==== CONECTAR WIFI ====
wifi.reset()
if wifi.connect(SSID, PASW):
    lcd.clear(lcd.WHITE)
    lcd.draw_string(10, 10, "WiFi conectado", lcd.BLACK, lcd.WHITE)
    print("WiFi conectado:", wifi.nic.ifconfig())
else:
    lcd.clear(lcd.RED)
    lcd.draw_string(10, 10, "Error WiFi", lcd.WHITE, lcd.RED)
    raise Exception("No se pudo conectar al WiFi")

# ==== RMS para detección de sonido ====
def rms(samples):
    """Calcula el nivel RMS del buffer"""
    sum_sq = 0
    for i in range(0, len(samples), 2):
        s = samples[i] | (samples[i+1] << 8)
        if s >= 32768:
            s -= 65536
        sum_sq += s * s
    return math.sqrt(sum_sq / (len(samples)//2))

# ==== GRABAR AUDIO ====
def grabar_audio():
    recorder = audio.Audio(path="/sd/record3.wav", is_create=True, samplerate=SAMPLE_RATE)
    queue = []
    frame_cnt = RECORD_TIME * SAMPLE_RATE // SAMPLE_POINTS

    for i in range(frame_cnt):
        tmp = rx.record(SAMPLE_POINTS * WAV_CH)
        if len(queue) > 0:
            recorder.record(queue[0])
            queue.pop(0)
        rx.wait_record()
        queue.append(tmp)
    recorder.finish()
    print("Grabación lista")

# ==== ENVIAR ====
def enviar_audio():
    FILENAME = "/sd/record3.wav"
    size = os.stat(FILENAME)[6]
    print("Enviando archivo de", size, "bytes")

    with open(FILENAME, "rb") as f:
        s = socket.socket()
        s.settimeout(10)  # Aumentamos timeout de conexión
        s.connect(socket.getaddrinfo(SERVER_IP, SERVER_PORT)[0][-1])
        header = (
            "POST /upload HTTP/1.1\r\n"
            "Host: {}\r\n"
            "Content-Type: application/octet-stream\r\n"
            "Content-Length: {}\r\n\r\n"
        ).format(SERVER_IP, size)
        s.send(header)
        while True:
            chunk = f.read(512)
            if not chunk:
                break
            s.send(chunk)
        response = s.recv(1024)
        s.close()

    # === Limpiar respuesta HTTP ===
    try:
        response_str = response.decode()
        if "\r\n\r\n" in response_str:
            body = response_str.split("\r\n\r\n", 1)[1]
        else:
            body = response_str
        texto = body.strip()
        print("Texto:", texto)
        lcd.clear(lcd.WHITE)
        # dividir texto si es largo
        lines = []
        while len(texto) > 20:
            lines.append(texto[:20])
            texto = texto[20:]
        lines.append(texto)
        y = 10
        for line in lines:
            lcd.draw_string(10, y, line, lcd.BLACK, lcd.WHITE)
            y += 20
        return texto
    except Exception as e:
        print("Error al decodificar respuesta:", e)
        lcd.clear(lcd.RED)
        lcd.draw_string(10, 10, "Error al leer resp", lcd.WHITE, lcd.RED)
        return None

# ==== LOOP PRINCIPAL ====
lcd.clear(lcd.WHITE)
lcd.draw_string(10, 10, "Esperando sonido...", lcd.BLACK, lcd.WHITE)

while True:
    audio_block = rx.record(SAMPLE_POINTS * WAV_CH)
    buf = audio_block.to_bytes()
    vol = rms(buf)
    print("Volumen:", int(vol))

    # Mostrar volumen actual
    lcd.clear(lcd.WHITE)
    lcd.draw_string(10, 10, "Volumen: {}".format(int(vol)), lcd.BLACK, lcd.WHITE)

    if vol > SOUND_THRESHOLD:
        lcd.clear(lcd.YELLOW)
        lcd.draw_string(10, 10, "Grabando...", lcd.BLACK, lcd.YELLOW)
        grabar_audio()
        lcd.clear(lcd.BLUE)
        lcd.draw_string(10, 10, "Enviando...", lcd.WHITE, lcd.BLUE)
        texto = enviar_audio()
        lcd.clear(lcd.GREEN)
        if texto:
            lcd.draw_string(10, 10, texto, lcd.BLACK, lcd.GREEN)
        else:
            lcd.draw_string(10, 10, "Sin texto", lcd.BLACK, lcd.GREEN)
        time.sleep(3)
        lcd.clear(lcd.WHITE)
        lcd.draw_string(10, 10, "Esperando sonido...", lcd.BLACK, lcd.WHITE)

    time.sleep_ms(200)
