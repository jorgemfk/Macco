from Maix import MIC_ARRAY as mic
from fpioa_manager import fm
from machine import PWM, Timer
from Maix import GPIO
from board import board_info
import sensor, image, lcd, time

# CONFIG
MAX_ANGULO = 100
TIEMPO_ACTIVO_MS = 1 * 20 * 1000  # 5 minutos en milisegundos

# LED reloj mapeado a ejes: (X, -X, Y, -Y)
led_ejes = [
    (1.0, 0.0, 0.0, 0.0), (0.7, 0.0, 0.7, 0.0), (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.7, 0.7), (0.0, 0.7, 0.0, 0.7), (0.0, 1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0), (0.0, 0.7, 0.0, 0.7), (0.0, 0.0, 0.7, 0.7),
    (0.0, 0.0, 1.0, 0.0), (0.7, 0.0, 0.7, 0.0), (1.0, 0.0, 0.0, 0.0),
]

servo_pins = {
    'X':   17,
    '-X':  35,
    'Y':   34,
    '-Y':  33,
}

colores = {
    'X':   (255, 0, 0),
    '-X':  (0, 255, 0),
    'Y':   (0, 0, 255),
    '-Y':  (255, 255, 0),
}

# REGISTRO DE PINES
fm.register(17, fm.fpioa.GPIO0)
fm.register(35, fm.fpioa.GPIO1)
fm.register(34, fm.fpioa.GPIO2)
fm.register(33, fm.fpioa.GPIO3)

# INICIALIZACIÓN
lcd.init()
mic.init()
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
sensor.skip_frames(time=2000)

# SERVOS
servo_pwms = {
    'X':   PWM(Timer(Timer.TIMER0, Timer.CHANNEL0, mode=Timer.MODE_PWM), freq=50, duty=0, pin=17),
    '-X':  PWM(Timer(Timer.TIMER1, Timer.CHANNEL0, mode=Timer.MODE_PWM), freq=50, duty=0, pin=35),
    'Y':   PWM(Timer(Timer.TIMER2, Timer.CHANNEL0, mode=Timer.MODE_PWM), freq=50, duty=0, pin=34),
    '-Y':  PWM(Timer(Timer.TIMER0, Timer.CHANNEL1, mode=Timer.MODE_PWM), freq=50, duty=0, pin=33),
}
estado_servo = {eje: 0 for eje in servo_pins.keys()}

# FUNCIONES

def mover_servo(pwm, grados):
    grados = max(0, min(grados, MAX_ANGULO))
    pulse = 500 + int((grados / MAX_ANGULO) * 2000)
    duty = int((pulse / 20000.0) * 100)
    pwm.duty(duty)

def calcular_angulos_direccion(leds):
    pesos = {'X': 0, '-X': 0, 'Y': 0, '-Y': 0}
    for i, intensidad in enumerate(leds):
        px, nx, py, ny = led_ejes[i]
        pesos['X'] += intensidad * px
        pesos['-X'] += intensidad * nx
        pesos['Y'] += intensidad * py
        pesos['-Y'] += intensidad * ny
    max_val = max(pesos.values())
    if max_val == 0:
        return {k: 0 for k in pesos}
    for k in pesos:
        pesos[k] = int((pesos[k] / max_val) * MAX_ANGULO)
    return pesos

# DETECCIÓN DE MOVIMIENTO
ref_img = sensor.snapshot()
ultimo_movimiento = 0
activo = False

# LOOP PRINCIPAL
while True:
    imga = mic.get_map()
    leds = mic.get_dir(imga)
    img = sensor.snapshot()
    hist = img.get_histogram()
    stats = hist.get_statistics()
    #ref_img = img.copy()
    print(leds)
    # Movimiento si varianza supera un umbral (ajustable)
    if stats.mean() > 40: #stats.stdev() > 15:
        print("Movimiento detectado")
        ultimo_movimiento = time.ticks_ms()
        activo = True
    elif time.ticks_diff(time.ticks_ms(), ultimo_movimiento) > TIEMPO_ACTIVO_MS:
        activo = False

    if activo:
        grados = calcular_angulos_direccion(leds)

        for eje in grados:
            mover_servo(servo_pwms[eje], grados[eje])
            estado_servo[eje] = grados[eje]
    else:
        grados = {k: 0 for k in servo_pins}
        for eje in grados:
            mover_servo(servo_pwms[eje], 0)
            estado_servo[eje] = 0

    # LED combinando color
    r, g, b = 0, 0, 0
    for eje in grados:
        if grados[eje] > 10:
            cr, cg, cb = colores[eje]
            r += cr
            g += cg
            b += cb
    mic.set_led(leds, (min(r, 255), min(g, 255), min(b, 255)))

    # Mostrar visualización de mic
    lcd.display(imga.resize(160, 160).to_rainbow(1))
    time.sleep(0.5)
