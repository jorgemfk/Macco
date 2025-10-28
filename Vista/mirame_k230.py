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
        #host = "192.168.1.224"
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
        if dets:
            resumen = {}
            for det, emotion in zip(dets, emotions):
                x, y, w, h = map(lambda x: int(round(x, 0)), det[:4])
                x = x * self.display_size[0] // self.rgb888p_size[0]
                y = y * self.display_size[1] // self.rgb888p_size[1]
                w = w * self.display_size[0] // self.rgb888p_size[0]
                h = h * self.display_size[1] // self.rgb888p_size[1]

                # Rectángulo del rostro
                pl.osd_img.draw_rectangle(x, y, w, h, color=(255, 0, 0, 255), thickness=2)
                # Texto centrado arriba
                text_x = x + w // 2 - len(emotion) * 8 // 2
                text_y = max(0, y - 25)
                pl.osd_img.draw_string(text_x, text_y, emotion,
                                       color=(255,255,0,255), scale=3)
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
    pl.create()
    display_size = pl.get_display_size()

    fe = FaceEmotion(face_det_kmodel_path, face_emotion_kmodel_path,
                     face_det_input_size, emotion_input_size, anchors,
                     confidence_threshold, nms_threshold,
                     rgb888p_size, display_size)
    WIFI_Connect()

    while True:
        with ScopedTiming("total",1):
            img = pl.get_frame()                # Captura frame
            dets, emotions = fe.run(img)        # Inferencia
            fe.draw_result(pl, dets, emotions)  # Dibuja resultados
            pl.show_image()                     # Muestra en pantalla
            procesar_envios_pendientes()
            gc.collect()

    fe.face_det.deinit()
    fe.face_emotion.deinit()
    pl.destroy()
