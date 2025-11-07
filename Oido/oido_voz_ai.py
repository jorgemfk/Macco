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
RECORD_TIME = 4  # segundos
SAMPLE_POINTS = 2048
WAV_CH = 2
SOUND_THRESHOLD = 80  # Ajusta según tu entorno

# ==== INICIALIZACIÓN LCD ====
lcd.init()
lcd.clear(lcd.WHITE)
lcd.draw_string(10, 10, "Inicializando...", lcd.BLACK)

# ==== CONFIGURAR AUDIO ====
fm.register(20, fm.fpioa.I2S0_IN_D0, force=True)
fm.register(19, fm.fpioa.I2S0_WS, force=True)
fm.register(18, fm.fpioa.I2S0_SCLK, force=True)
rx = I2S(I2S.DEVICE_0)
rx.channel_config(rx.CHANNEL_0, rx.RECEIVER, align_mode=I2S.STANDARD_MODE)
rx.set_sample_rate(SAMPLE_RATE)

# ==== FUNCIÓN WiFi ====
class wifi():
    nic = None
    def reset():
        fm.register(25,fm.fpioa.GPIOHS10)
        fm.register(8,fm.fpioa.GPIOHS11)
        fm.register(9,fm.fpioa.GPIOHS12)
        fm.register(28,fm.fpioa.SPI1_D0)
        fm.register(26,fm.fpioa.SPI1_D1)
        fm.register(27,fm.fpioa.SPI1_SCLK)
        wifi.nic = network.ESP32_SPI(
            cs=fm.fpioa.GPIOHS10,
            rst=fm.fpioa.GPIOHS11,
            rdy=fm.fpioa.GPIOHS12,
            spi=1)
    def connect(ssid, pasw):
        wifi.nic.connect(ssid, pasw)
        for _ in range(20):
            if wifi.nic.isconnected():
                return True
            time.sleep_ms(500)
        return False

wifi.reset()
wifi.connect(SSID, PASW)
print("WiFi conectado:", wifi.nic.ifconfig())
lcd.draw_string(10, 30, "WiFi conectado", lcd.BLACK)

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

# ==== ENVIAR AUDIO EN BINARIO ====
def enviar_audio():
    FILENAME = "/sd/record3.wav"
    size = os.stat(FILENAME)[6]
    print("Enviando archivo de", size, "bytes")

    with open(FILENAME, "rb") as f:
        s = socket.socket()
        s.connect(socket.getaddrinfo(SERVER_IP, SERVER_PORT)[0][-1])
        header = (
            "POST /upload HTTP/1.1\r\n"
            "Host: {}\r\n"
            "Content-Type: application/octet-stream\r\n"
            "Content-Length: {}\r\n\r\n"
        ).format(SERVER_IP, size)
        s.send(header)
        while True:
            chunk = f.read(1024)
            if not chunk:
                break
            s.send(chunk)
        response = s.recv(512)
        s.close()
        print("Respuesta del servidor:", response)
    return "OK"

# ==== LOOP PRINCIPAL ====
lcd.clear(lcd.WHITE)
lcd.draw_string(10, 10, "Esperando sonido...", lcd.BLACK)

while True:
    audio_block = rx.record(SAMPLE_POINTS * WAV_CH)
    buf = audio_block.to_bytes()
    vol = rms(buf)
    print("Volumen:", int(vol))

    if vol > SOUND_THRESHOLD:
        lcd.clear(lcd.YELLOW)
        lcd.draw_string(10, 10, "Grabando...", lcd.BLACK)
        grabar_audio()
        lcd.clear(lcd.BLUE)
        lcd.draw_string(10, 10, "Enviando...", lcd.WHITE)
        enviar_audio()
        lcd.clear(lcd.GREEN)
        lcd.draw_string(10, 10, "Listo. Esperando...", lcd.BLACK)
        time.sleep(2)
