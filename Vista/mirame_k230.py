# ==========================================================
#  01Studio CanMV K230
# mirame: pieza macco oaxaca
# ==========================================================

from libs.PipeLine import PipeLine
from libs.AIBase import AIBase
from libs.AI2D import Ai2d
from libs.Utils import *
import os, sys, ujson, gc, math
from media.media import *
import nncase_runtime as nn
import ulab.numpy as np
import image
import aidemo
import network,time
from machine import Pin
import ujson
import usocket
import _thread
from machine import I2C
import time
import ustruct

#SERVO CONFIG



class PCA9685:
    def __init__(self, i2c, address=0x40):
        self.i2c = i2c
        self.address = address
        self.reset()

    def _write(self, address, value):
        print(address)
        print(value)
        print("======")
        self.i2c.writeto_mem(self.address, address, bytearray([value]))

    def _read(self, address):
        return self.i2c.readfrom_mem(self.address, address, 1)[0]

    def reset(self):
        self._write(0x00, 0x00) # Mode1

    def freq(self, freq=None):
        if freq is None:
            return int(25000000.0 / 4096 / (self._read(0xfe) - 0.5))
        prescale = int(25000000.0 / 4096.0 / freq + 0.5)
        old_mode = self._read(0x00) # Mode 1
        self._write(0x00, (old_mode & 0x7F) | 0x10) # Mode 1, sleep
        self._write(0xfe, prescale) # Prescale
        self._write(0x00, old_mode) # Mode 1
        time.sleep_us(5)
        self._write(0x00, old_mode | 0xa1) # Mode 1, autoincrement on

    def pwm(self, index, on=None, off=None):
        if on is None or off is None:
            data = self.i2c.readfrom_mem(self.address, 0x06 + 4 * index, 4)
            return ustruct.unpack('<HH', data)
        data = ustruct.pack('<HH', on, off)
        self.i2c.writeto_mem(self.address, 0x06 + 4 * index,  data)

    def duty(self, index, value=None, invert=False):
        if value is None:
            pwm = self.pwm(index)
            if pwm == (0, 4096):
                value = 0
            elif pwm == (4096, 0):
                value = 4095
            value = pwm[1]
            if invert:
                value = 4095 - value
            return value
        if not 0 <= value <= 4095:
            raise ValueError("Out of range")
        if invert:
            value = 4095 - value
        if value == 0:
            self.pwm(index, 0, 4096)
        elif value == 4095:
            self.pwm(index, 4096, 0)
        else:
            self.pwm(index, 0, value)



class Servos:
    def __init__(self, i2c, address=0x40, freq=50, min_us=500, max_us=2500,
                 degrees=180):
        self.period = 1000000 / freq
        self.min_duty = self._us2duty(min_us)
        self.max_duty = self._us2duty(max_us)
        self.degrees = degrees
        self.freq = freq
        self.pca9685 = PCA9685(i2c, address)
        self.pca9685.freq(freq)

    def _us2duty(self, value):
        return int(4095 * value / self.period)

    def position(self, index, degrees=None, radians=None, us=None, duty=None):
        span = self.max_duty - self.min_duty
        if degrees is not None:
            duty = self.min_duty + span * degrees / self.degrees
        elif radians is not None:
            duty = self.min_duty + span * radians / math.radians(self.degrees)
        elif us is not None:
            duty = self._us2duty(us)
        elif duty is not None:
            pass
        else:
            return self.pca9685.duty(index)
        duty = min(self.max_duty, max(self.min_duty, int(duty)))
        self.pca9685.duty(index, duty)

    def release(self, index):
        self.pca9685.duty(index, 0)

#i2c1 = I2C(I2C.I2C0, mode=I2C.MODE_MASTER,scl=7, sda=6)
i2c1 = I2C(2, scl = 11, sda = 12, freq = 100000, timeout = 1000)
print(i2c1.scan())

s=Servos(i2c1)

# ===============================
# SERVO 5 - ESTADO
# ===============================
SERVO5_IDLE = 0
SERVO5_ON = 1
SERVO5_OFF = 2

servo5_state = SERVO5_IDLE
servo5_timer = 0
def update_servo5(face_detected):
    global servo5_state, servo5_timer

    now = time.ticks_ms()

    # Estado IDLE → aparece cara
    if servo5_state == SERVO5_IDLE:
        if face_detected:
            s.position(5, 180)
            servo5_timer = now
            servo5_state = SERVO5_ON
            print("[SERVO5] ON 180°")

    # Estado ON → esperar 5 s
    elif servo5_state == SERVO5_ON:
        if time.ticks_diff(now, servo5_timer) >= 5000:
            s.position(5, 0)
            servo5_timer = now
            servo5_state = SERVO5_OFF
            print("[SERVO5] OFF 0°")

    # Estado OFF → esperar 5 s antes de rearmar
    elif servo5_state == SERVO5_OFF:
        if time.ticks_diff(now, servo5_timer) >= 5000:
            servo5_state = SERVO5_IDLE
            print("[SERVO5] READY")

# ==========================================================
# red
# ==========================================================

pendientes = []
ultimo_envio = 0



def enviar_emociones_hilo(resumen):
    _thread.start_new_thread(enviar_emociones, (resumen,))

def enviar_emociones_async(resumen):
    global pendientes
    pendientes.append(resumen)

def procesar_envios_pendientes():
    global pendientes, ultimo_envio
    if len(pendientes) > 0:
        ahora = time.ticks_ms()
        if time.ticks_diff(ahora, ultimo_envio) > 2000:  # cada 2 s
            resumen = pendientes.pop(0)
            enviar_emociones_hilo(resumen)
            ultimo_envio = ahora

def enviar_emociones(resumen):
    try:
        data = ujson.dumps({"emociones": resumen})
        #host = "192.168.1.207"
        host = "192.168.0.200"
        port = 5820
        path = "/emociones"

        s = usocket.socket()
        s.settimeout(3.0)  # evita que se bloquee demasiado
        s.connect((host, port))
        s.send(b"POST %s HTTP/1.0\r\n" % path.encode())
        s.send(b"Host: %s\r\n" % host.encode())
        s.send(b"Content-Type: application/json\r\n")
        s.send(b"Content-Length: %d\r\n\r\n" % len(data))
        s.send(data.encode())
        s.close()
        print(" POST enviado")
    except Exception as e:
        print(" Error POST:", e)



def WIFI_Connect():

    WIFI_LED=Pin(52, Pin.OUT)

    wlan = network.WLAN(network.STA_IF)
    #wlan.disconnect()        # 🔹 Rompe cualquier conexión previa
    time.sleep(0.5)
    wlan.active(True)

    if not wlan.isconnected():

        print('conectando...')

        for i in range(10):

            #wlan.connect('INFINITUM47A4_2.4', 'eFwN3s9VPP')
            wlan.connect('Bait_F-02_1521', '1234567890')
            if wlan.isconnected():
                break

    if wlan.isconnected():

        print('connectado')
        pl.osd_img.draw_string(0, 0, 'conectado',
                               color=(255,255,0,255), scale=4)

        WIFI_LED.value(1)


        while wlan.ifconfig()[0] == '0.0.0.0':
            pass


        print('network :', wlan.ifconfig())

    else:


        for i in range(3):
            WIFI_LED.value(1)
            time.sleep_ms(300)
            WIFI_LED.value(0)
            time.sleep_ms(300)

        wlan.active(False)
#calculo de coordenada
# Función para mapear valores
def map_value(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)


EMOTION_COLORS = {
    "Enojo":      (255,   0,   0, 255),
    "Asco":       (120, 200,  60, 255),
    "Miedo":      (40,   80, 160, 255),
    "Felicidad":  (255, 220,   0, 255),
    "Tristeza":   (100, 130, 160, 255),
    "Sorpresa":   (220,  80, 200, 255),
    "Neutral":    (200, 200, 200, 255),
}

# ==========================================================
# Clase de detección de rostros
# ==========================================================
class FaceDetApp(AIBase):
    def __init__(self, kmodel_path, model_input_size, anchors,
                 confidence_threshold=0.25, nms_threshold=0.3,
                 rgb888p_size=[1280,720], display_size=[1920,1080], debug_mode=0):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.anchors = anchors
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0],16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0],16), display_size[1]]
        self.debug_mode = debug_mode
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,
                                 nn.ai2d_format.NCHW_FMT,
                                 np.uint8, np.uint8)

    def config_preprocess(self, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            top, bottom, left, right, _ = letterbox_pad_param(
                self.rgb888p_size, self.model_input_size)
            self.ai2d.pad([0,0,0,0, top,bottom,left,right], 0, [114,114,114])
            self.ai2d.resize(nn.interp_method.tf_bilinear,
                             nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],
                            [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            res = aidemo.face_det_post_process(
                self.confidence_threshold, self.nms_threshold,
                self.model_input_size[0], self.anchors,
                self.rgb888p_size, results)
            if len(res)==0:
                return []
            return res[0]

# ==========================================================
# Clase de reconocimiento de emociones
# ==========================================================
class FaceEmotionApp(AIBase):
    def __init__(self, kmodel_path, model_input_size,
                 rgb888p_size=[1920,1080], display_size=[1920,1080], debug_mode=0):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0],16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0],16), display_size[1]]
        self.debug_mode = debug_mode
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,
                                 nn.ai2d_format.NCHW_FMT,
                                 np.uint8, np.uint8)

    def config_preprocess(self, det, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            x, y, w, h = map(lambda x: int(round(x, 0)), det[:4])
            self.ai2d.crop(x, y, w, h)
            self.ai2d.resize(nn.interp_method.tf_bilinear,
                             nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],
                            [1,3,self.model_input_size[1],self.model_input_size[0]])

    # ---  Postprocesamiento corregido (usa softmax)
    def postprocess(self, results):
        #print("Res:", results)
        logits = results[0][0]  # (1,7)
        exp_vals = np.exp(logits - np.max(logits))
        probs = exp_vals / np.sum(exp_vals)
        emotion_labels = ["Enojo", "Asco", "Miedo", "Felicidad", "Tristeza", "Sorpresa", "Neutral"]
        emotion_id = int(np.argmax(probs))
        print("Probs:", probs, "->", emotion_labels[emotion_id])
        return emotion_labels[emotion_id]

# ==========================================================
# Clase principal FaceEmotion (detección + emoción)
# ==========================================================

# GESTOS EMOCIONALES CON SERVOS 3,4
gesture_queue = []
gesture_active = False
gesture_timer = 0
gesture_step_delay = 40  # dinamico

def update_gesture_scheduler():
    global gesture_timer, gesture_active

    if not gesture_queue:
        gesture_active = False
        return

    now = time.ticks_ms()
    if time.ticks_diff(now, gesture_timer) >= gesture_step_delay:
        ch, pos = gesture_queue.pop(0)
        s.position(ch, pos)
        gesture_timer = now


def enqueue_move(ch, start, end, steps):
    delta = (end - start) / steps
    pos = start
    for _ in range(steps):
        pos += delta
        gesture_queue.append((ch, int(pos)))


SERVO_EJE_Y   = 3   # movimiento vertical (0–40°)
SERVO_CABEZA  = 4   # head tilt tipo perro (0–60°)
# Posiciones neutras
NEUTRO_Y     = 20
NEUTRO_TILT  = 30

def schedule_emotional_gesture(emotion):
    global gesture_active, gesture_step_delay

    if gesture_active:
        return

    gesture_active = True

    # ===== VALORES BASE =====
    y0 = s.position(SERVO_EJE_Y)
    t0 = s.position(SERVO_CABEZA)

    # =========================
    if emotion == "Felicidad":
        gesture_step_delay = 28   # rápido, fluido

        # head tilt amplio y rítmico
        for _ in range(2):
            enqueue_move(SERVO_CABEZA, t0, 50, 5)
            enqueue_move(SERVO_CABEZA, 50, 25, 5)

        # leve elevación de eje Y
        enqueue_move(SERVO_EJE_Y, y0, 32, 6)

    # =========================
    elif emotion == "Tristeza":
        gesture_step_delay = 70   # lento, pesado

        # caída progresiva
        enqueue_move(SERVO_EJE_Y, y0, 6, 10)
        enqueue_move(SERVO_CABEZA, t0, 18, 8)

    # =========================
    elif emotion == "Miedo":
        gesture_step_delay = 25   # nervioso

        # retracción rápida
        enqueue_move(SERVO_EJE_Y, y0, 4, 6)
        enqueue_move(SERVO_CABEZA, t0, 12, 6)

        # temblor corto
        for _ in range(3):
            enqueue_move(SERVO_CABEZA, 12, 18, 2)
            enqueue_move(SERVO_CABEZA, 18, 12, 2)

    # =========================
    elif emotion == "Enojo":
        gesture_step_delay = 20   # brusco

        # golpe hacia arriba
        enqueue_move(SERVO_EJE_Y, y0, 38, 4)
        enqueue_move(SERVO_CABEZA, t0, 35, 3)

        # micro sacudida final
        enqueue_move(SERVO_CABEZA, 35, 30, 2)

    # =========================
    elif emotion == "Sorpresa":
        gesture_step_delay = 15   # muy rápido

        # apertura súbita
        enqueue_move(SERVO_EJE_Y, y0, 42, 3)
        enqueue_move(SERVO_CABEZA, t0, 55, 3)

        # freeze breve
        enqueue_move(SERVO_CABEZA, 55, 55, 3)

    # =========================
    elif emotion == "Asco":
        gesture_step_delay = 45   # irregular

        # retiro + giro evasivo
        enqueue_move(SERVO_EJE_Y, y0, 10, 6)
        enqueue_move(SERVO_CABEZA, t0, 48, 4)
        enqueue_move(SERVO_CABEZA, 48, 22, 4)

    # =========================
    elif emotion == "Neutral":
        gesture_step_delay = 60   # respirado

        enqueue_move(SERVO_EJE_Y, y0, NEUTRO_Y, 8)
        enqueue_move(SERVO_CABEZA, t0, NEUTRO_TILT, 8)


class FaceEmotion:
    def __init__(self, face_det_kmodel, face_emotion_kmodel,
                 det_input_size, emotion_input_size, anchors,
                 confidence_threshold=0.25, nms_threshold=0.3,
                 rgb888p_size=[1920,1080], display_size=[1920,1080], debug_mode=0):
        self.face_det = FaceDetApp(face_det_kmodel, det_input_size, anchors,
                                   confidence_threshold, nms_threshold,
                                   rgb888p_size, display_size, debug_mode)
        self.face_emotion = FaceEmotionApp(face_emotion_kmodel, emotion_input_size,
                                           rgb888p_size, display_size, debug_mode)
        self.face_det.config_preprocess()
        self.rgb888p_size = rgb888p_size
        self.display_size = display_size
        self.last_resumen = None
        self.last_send_time = 0
        self.stable_counter = 0         # contador de estabilidad
        self.required_stable_frames = 3 # mínimo de frames iguales antes de enviar

    def run(self, img):
        dets = self.face_det.run(img)
        emotions = []
        for det in dets:
            self.face_emotion.config_preprocess(det)
            emotion_label = self.face_emotion.run(img)
            emotions.append(emotion_label)
        return dets, emotions

    def draw_result(self, pl, dets, emotions):
        pl.osd_img.clear()
        update_servo5(face_detected = bool(dets))
        update_gesture_scheduler()
        if dets:
            resumen = {}
            cara=True
            for det, emotion in zip(dets, emotions):
                x, y, w, h = map(lambda x: int(round(x, 0)), det[:4])
                #donde esta la 1er cara
                if cara:
                    half_width = w // 2
                    half_height = h // 2

                    # Centro del rostro en la imagen
                    face_center_pan = x + half_width
                    face_center_tilt = y + half_height

                    # Convertir coordenadas a ángulos de servo
                    My_centerx = map_value(face_center_pan, half_width, self.rgb888p_size[0]- half_width, 120, 0)
                    My_centerxx = map_value(face_center_pan, half_width, self.rgb888p_size[0]- half_width, 90, 0)
                    My_centerxr = map_value(face_center_pan, half_width, self.rgb888p_size[0]- half_width, 40, 0)

                    My_centery = map_value(face_center_tilt, half_height,  self.rgb888p_size[1]- half_height, 50, 0)
                    My_centerz = map_value(face_center_tilt, half_height,  self.rgb888p_size[1]- half_height, 0, 30)

                    print("X {}".format(My_centerx))
                    print("Y {}".format(My_centery))
                    print("F {}".format(self.display_size[0]))
                    print("FW {}".format(self.rgb888p_size[0]))
                    print("W {}".format(self.display_size[1]))
                    print("WF {}".format(self.rgb888p_size[1]))
                    print(self.display_size[0] // self.rgb888p_size[0])
                    # Mover servos
                    s.position(0, My_centerx)
                    s.position(1, My_centery)
                    #time.sleep(0.06 )
                    s.position(2,  My_centerz)
                    #s.position(2, My_centerz)
                    #s.position(3, My_centerxx)
                    #s.position(4, My_centerxr)
                    time.sleep(0.06 )
                    schedule_emotional_gesture(emotion)
                    cara = False
                x = x * self.display_size[0] // self.rgb888p_size[0]
                y = y * self.display_size[1] // self.rgb888p_size[1]
                w = w * self.display_size[0] // self.rgb888p_size[0]
                h = h * self.display_size[1] // self.rgb888p_size[1]

                # Rectángulo del rostro
                color = EMOTION_COLORS.get(emotion, (255,255,255,255))
                pl.osd_img.draw_rectangle(x, y, w, h, color=color, thickness=2)
                # Texto centrado arriba
                text_x = x + w // 2 - len(emotion) * 8 // 2
                text_y = max(0, y - 25)
                pl.osd_img.draw_string(text_x, text_y, emotion,
                                       color=(255,255,0,255), scale=4)
                # --- Contar emociones ---
                resumen[emotion] = resumen.get(emotion, 0) + 1

            current_time = time.ticks_ms()
            tiempo_desde_ultimo = time.ticks_diff(current_time, self.last_send_time)

            # --- Control de estabilidad ---
            if resumen == self.last_resumen:
                self.stable_counter += 1
            else:
                self.stable_counter = 0
            self.last_resumen = resumen

            # --- Solo envía si la emoción se mantuvo estable N frames y pasaron 2 s ---
            if self.stable_counter >= self.required_stable_frames and tiempo_desde_ultimo > 2000:
                print("Emociones estables:", resumen)
                enviar_emociones_async(resumen)
                self.last_send_time = current_time
                self.stable_counter = 0  # Reinicia después de enviar

# ==========================================================
# MAIN
# ==========================================================
if __name__=="__main__":
    display_mode = "lcd"
    display_size = [800, 480]
    #bajar modelos de https://www.kendryte.com/en/model/library
    face_det_kmodel_path = "/sdcard/examples/kmodel/face_detection_320.kmodel"
    face_emotion_kmodel_path = "/sdcard/examples/kmodel/face_emotion.kmodel"

    anchors_path = "/sdcard/examples/utils/prior_data_320.bin"
    anchor_len, det_dim = 4200, 4
    anchors = np.fromfile(anchors_path, dtype=np.float).reshape((anchor_len, det_dim))

    rgb888p_size = [1920,1080]
    face_det_input_size = [320,320]
    emotion_input_size = [224,224]
    confidence_threshold = 0.5
    nms_threshold = 0.2

    pl = PipeLine(rgb888p_size=rgb888p_size,
                  display_size=display_size,
                  display_mode=display_mode)

    pl.create(hmirror=True,   # espejo
              vflip=False )
    display_size = pl.get_display_size()

    fe = FaceEmotion(face_det_kmodel_path, face_emotion_kmodel_path,
                     face_det_input_size, emotion_input_size, anchors,
                     confidence_threshold, nms_threshold,
                     rgb888p_size, display_size)
    WIFI_Connect()

    while True:
        with ScopedTiming("total",1):
            img = pl.get_frame()                # Captura la frame
            dets, emotions = fe.run(img)        # Inferencia
            fe.draw_result(pl, dets, emotions)  # Dibuja resultados
            pl.show_image()                     # Muestra en pantalla
            procesar_envios_pendientes()
            gc.collect()

    fe.face_det.deinit()
    fe.face_emotion.deinit()
    pl.destroy()
