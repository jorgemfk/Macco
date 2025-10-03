from Maix import MIC_ARRAY as mic
import lcd
from machine import PWM, Timer
from fpioa_manager import fm
import time

MAX_ANGULO = 100

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

# Registrar pines
fm.register(17, fm.fpioa.GPIO0)
fm.register(35, fm.fpioa.GPIO1)
fm.register(34, fm.fpioa.GPIO2)
fm.register(33, fm.fpioa.GPIO3)

# Inicializar
lcd.init()
mic.init()

# PWM por eje
servo_pwms = {
    'X':   PWM(Timer(Timer.TIMER0, Timer.CHANNEL0, mode=Timer.MODE_PWM), freq=50, duty=0, pin=17),
    '-X':  PWM(Timer(Timer.TIMER1, Timer.CHANNEL0, mode=Timer.MODE_PWM), freq=50, duty=0, pin=35),
    'Y':   PWM(Timer(Timer.TIMER2, Timer.CHANNEL0, mode=Timer.MODE_PWM), freq=50, duty=0, pin=34),
    '-Y':  PWM(Timer(Timer.TIMER0, Timer.CHANNEL1, mode=Timer.MODE_PWM), freq=50, duty=0, pin=33),
}

estado_servo = {eje: 0 for eje in servo_pins}

# Asignar color por eje
colores = {
    'X':   (255, 0, 0),     # Rojo
    '-X':  (0, 255, 0),     # Verde
    'Y':   (0, 0, 255),     # Azul
    '-Y':  (255, 255, 0),   # Amarillo
}

def mover_servo(pwm, grados):
    grados = max(0, min(grados, MAX_ANGULO))
    pulse = 500 + int((grados / MAX_ANGULO) * 2000)
    duty = int((pulse / 20000.0) * 100)
    pwm.duty(duty)

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

    # Actualizar servos
    for eje in ['X', '-X', 'Y', '-Y']:
        if grados[eje] != estado_servo[eje]:
            mover_servo(servo_pwms[eje], grados[eje])
            estado_servo[eje] = grados[eje]

    # Determinar color combinado
    r, g, b = 0, 0, 0
    for eje in grados:
        if grados[eje] > 10:  # Considerar solo activaciones significativas
            cr, cg, cb = colores[eje]
            r += cr
            g += cg
            b += cb
    r, g, b = min(r, 255), min(g, 255), min(b, 255)
    mic.set_led(leds, (r, g, b))

    # Mostrar visualización del mapa de sonido
    imgc = imga.resize(160, 160).to_rainbow(1)
    lcd.display(imgc)
    time.sleep(0.5);
