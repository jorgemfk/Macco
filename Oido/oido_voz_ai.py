import image, lcd, time, audio, math, ubinascii, ujson, socket, os
from Maix import I2S, GPIO
from fpioa_manager import fm
import network

# ---------- CONFIGURACIÓN ----------
SSID = 'INFINITUM47A4_2.4'
KEY  = 'eFwN3s9VPP'
SERVER_IP = '192.168.1.207'  # IP de la Raspberry Pi
SERVER_PORT = 5821

SOUND_THRESHOLD = 5000   # Nivel de sonido para disparar grabación
RECORD_SECONDS = 4
SAMPLE_RATE = 16000
SAMPLE_POINTS = 2048
WAV_CH = 2
WAV_PATH = "/sd/record.wav"

# ---------- LCD ----------
lcd.init()
lcd.clear(lcd.WHITE)
lcd.draw_string(10, 10, "Esperando sonido fuerte...", lcd.BLACK)

# ---------- CONFIG MIC ----------
fm.register(20, fm.fpioa.I2S0_IN_D0, force=True)
fm.register(19, fm.fpioa.I2S0_WS, force=True)
fm.register(18, fm.fpioa.I2S0_SCLK, force=True)

rx = I2S(I2S.DEVICE_0)
rx.channel_config(rx.CHANNEL_0, rx.RECEIVER, align_mode=I2S.STANDARD_MODE)
rx.set_sample_rate(SAMPLE_RATE)

# ---------- CONFIG WIFI (ESP8285) ----------
fm.register(8, fm.fpioa.GPIOHS0, force=True)
wifi_en = GPIO(GPIO.GPIOHS0, GPIO.OUT)
wifi_en.value(1)
time.sleep_ms(500)

nic = network.ESP8285()
nic.connect(SSID, KEY)
print("Conectando WiFi...")
while not nic.isconnected():
    time.sleep(0.5)
print("WiFi OK:", nic.ifconfig())
lcd.draw_string(10, 30, "WiFi conectado!", lcd.BLACK)

# ---------- FUNCIONES ----------

def rms(samples):
    """Calcula el volumen RMS del buffer"""
    sum_sq = 0
    for i in range(0, len(samples), 2):
        s = samples[i] | (samples[i+1] << 8)
        if s >= 32768:
            s -= 65536
        sum_sq += s * s
    return math.sqrt(sum_sq / (len(samples)//2))

def grabar_audio():
    """Graba audio durante RECORD_SECONDS segundos"""
    recorder = audio.Audio(path=WAV_PATH, is_create=True, samplerate=SAMPLE_RATE)
    frame_cnt = RECORD_SECONDS * SAMPLE_RATE // SAMPLE_POINTS
    queue = []
    for i in range(frame_cnt):
        tmp = rx.record(SAMPLE_POINTS * WAV_CH)
        if queue:
            recorder.record(queue[0])
            queue.pop(0)
        rx.wait_record()
        queue.append(tmp)
    recorder.finish()
    print("Grabación completa:", WAV_PATH)

def enviar_audio():
    """Envía WAV al servidor y recibe transcripción"""
    with open(WAV_PATH, "rb") as f:
        data = f.read()

    b64 = ubinascii.b2a_base64(data).decode().replace("\n", "")
    payload = ujson.dumps({"filename": "record.wav", "data": b64})
    req = (
        "POST /upload HTTP/1.1\r\n"
        "Host: {}\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: {}\r\n\r\n{}"
    ).format(SERVER_IP, len(payload), payload)

    addr = socket.getaddrinfo(SERVER_IP, SERVER_PORT)[0][-1]
    s = socket.socket()
    try:
        s.connect(addr)
        s.send(req)
        response = s.recv(1024).decode()
        s.close()
        print("Respuesta:", response)
        # Extraer texto de respuesta JSON
        try:
            json_part = response.split("\r\n\r\n", 1)[1]
            reply = ujson.loads(json_part)
            texto = reply.get("text", "")
        except Exception as e:
            texto = "Error JSON"
        return texto
    except Exception as e:
        print("Error envío:", e)
        s.close()
        return "Error conexión"

# ---------- LOOP PRINCIPAL ----------

lcd.clear(lcd.WHITE)
lcd.draw_string(10, 10, "Esperando sonido fuerte...", lcd.BLACK)

while True:
    # Escuchar pequeños fragmentos para detectar volumen
    buf = rx.record(SAMPLE_POINTS * WAV_CH)
    vol = rms(buf)
    print("Volumen:", int(vol))

    if vol > SOUND_THRESHOLD:
        lcd.clear(lcd.YELLOW)
        lcd.draw_string(10, 10, "Grabando 4s...", lcd.BLACK)
        grabar_audio()
        lcd.clear(lcd.BLUE)
        lcd.draw_string(10, 10, "Enviando a servidor...", lcd.WHITE)
        texto = enviar_audio()
        lcd.clear(lcd.WHITE)
        lcd.draw_string(10, 10, "Texto:", lcd.BLACK)
        lcd.draw_string(10, 30, texto[:100], lcd.BLACK)
        print("Texto recibido:", texto)

        # Esperar silencio antes de seguir escuchando
        time.sleep(3)
        lcd.clear(lcd.WHITE)
        lcd.draw_string(10, 10, "Esperando sonido fuerte...", lcd.BLACK)
