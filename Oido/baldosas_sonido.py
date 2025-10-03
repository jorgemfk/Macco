from Maix import MIC_ARRAY as mic
import lcd
from machine import PWM, Timer
from fpioa_manager import fm
import time
import math

MAX_ANGULO = 100  # Ángulo máximo permitido

# Mapeo LED reloj → pesos por eje (X, -X, Y, -Y)
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

# Registrar pines
fm.register(17, fm.fpioa.GPIO0)
fm.register(35, fm.fpioa.GPIO1)
fm.register(34, fm.fpioa.GPIO2)
fm.register(33, fm.fpioa.GPIO3)

# Inicialización
lcd.init()
mic.init()

# Configuración de PWM con timers válidos
servo_pwms = {
    'X':   PWM(Timer(Timer.TIMER0, Timer.CHANNEL0, mode=Timer.MODE_PWM), freq=50, duty=0, pin=17),
    '-X':  PWM(Timer(Timer.TIMER1, Timer.CHANNEL0, mode=Timer.MODE_PWM), freq=50, duty=0, pin=35),
    'Y':   PWM(Timer(Timer.TIMER2, Timer.CHANNEL0, mode=Timer.MODE_PWM), freq=50, duty=0, pin=34),
    '-Y':  PWM(Timer(Timer.TIMER0, Timer.CHANNEL1, mode=Timer.MODE_PWM), freq=50, duty=0, pin=33),
}

estado_servo = {eje: 0 for eje in servo_pins.keys()}

def mover_servo(pwm, grados):
    grados = max(0, min(grados, MAX_ANGULO))
    pulse = 500 + int((grados / MAX_ANGULO) * 2000)
    duty = int((pulse / 20000.0) * 100)
    pwm.duty(duty)

def mover_servo_gradual(pwm, eje, meta_grado):
    actual = estado_servo[eje]
    if actual == meta_grado:
        return
    pasos = 20
    for i in range(pasos + 1):
        t = i / pasos
        interp = 0.5 - 0.5 * math.cos(math.pi * t)
        grado = int(actual + (meta_grado - actual) * interp)
        mover_servo(pwm, grado)
        time.sleep_ms(15)
    estado_servo[eje] = meta_grado

def calcular_angulos_direccion(leds):
    pesos = {'X': 0, '-X': 0, 'Y': 0, '-Y': 0}
    for i, intensidad in enumerate(leds):
        px, nx, py, ny = led_ejes[i]
        pesos['X']   += intensidad * px
        pesos['-X']  += intensidad * nx
        pesos['Y']   += intensidad * py
        pesos['-Y']  += intensidad * ny
    max_val = max(pesos.values())
    if max_val == 0:
        return {k: 0 for k in pesos}
    for k in pesos:
        pesos[k] = int((pesos[k] / max_val) * MAX_ANGULO)
    return pesos

# Bucle principal
while True:
    imga = mic.get_map()
    leds = mic.get_dir(imga)
    grados = calcular_angulos_direccion(leds)

    print("LEDs:", leds)
    print("Ángulos:", grados)

    for eje in ['X', '-X', 'Y', '-Y']:
        mover_servo_gradual(servo_pwms[eje], eje, grados[eje])

    imgc = imga.resize(160, 160).to_rainbow(1)
    lcd.display(imgc)
