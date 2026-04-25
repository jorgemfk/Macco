from Maix import MIC_ARRAY as mic
import lcd
from machine import I2C
import time
import math
import ustruct

lcd.init()
mic.init()

# ---------------- PCA9685 ----------------

class PCA9685:

    def __init__(self, i2c, address=0x40):
        self.i2c = i2c
        self.address = address
        self.reset()

    def _write(self, address, value):
        self.i2c.writeto_mem(self.address, address, bytearray([value]))

    def _read(self, address):
        return self.i2c.readfrom_mem(self.address, address, 1)[0]

    def reset(self):
        self._write(0x00, 0x00)

    def freq(self, freq):
        prescale = int(25000000.0 / 4096.0 / freq + 0.5)
        old_mode = self._read(0x00)

        self._write(0x00, (old_mode & 0x7F) | 0x10)
        self._write(0xfe, prescale)
        self._write(0x00, old_mode)

        time.sleep_us(5)

        self._write(0x00, old_mode | 0xa1)

    def pwm(self, index, on=None, off=None):

        if on is None or off is None:
            data = self.i2c.readfrom_mem(self.address, 0x06 + 4 * index, 4)
            return ustruct.unpack('<HH', data)

        data = ustruct.pack('<HH', on, off)
        self.i2c.writeto_mem(self.address, 0x06 + 4 * index, data)

    def duty(self, index, value):
        self.pwm(index, 0, value)


class Servos:

    def __init__(self, i2c, address=0x40, freq=50):

        self.period = 1000000 / freq

        self.min_us = 500
        self.max_us = 2500

        self.min_duty = int(4095 * self.min_us / self.period)
        self.max_duty = int(4095 * self.max_us / self.period)

        self.pca9685 = PCA9685(i2c, address)
        self.pca9685.freq(freq)

    def position(self, index, degrees):

        degrees = max(0, min(120, degrees))

        span = self.max_duty - self.min_duty
        duty = self.min_duty + span * degrees / 180

        self.pca9685.duty(index, int(duty))


# ---------------- I2C ----------------

i2c1 = I2C(I2C.I2C0, mode=I2C.MODE_MASTER, scl=7, sda=6)

servos = Servos(i2c1)

# bloqueo se servor para resetear a 0
servo_blocked = [False]*6
servo_release_time = [0]*6
RETORNO_MS = 600  # tiempo para llegar a 0
# ---------------- PARÁMETROS ORGÁNICOS ----------------

threshold = 3          # filtro ruido
alpha = 0.15           # suavizado movimiento
memory_decay = 0.96    # memoria sonido
explore_speed = 0.02   # exploración cuando no hay sonido

servo_angles = [10]*6
servo_targets = [10]*6

memory_x = 0
memory_y = 0

explore_angle = 0
last_reset = time.ticks_ms()
# ---------------- LOOP ----------------

while True:
    if time.ticks_diff(time.ticks_ms(), last_reset) > 600000:  # 10 min
        print("soft reset PCA9685")
        servos.pca9685.reset()
        servos.pca9685.freq(50)
        # reset mic
        mic.deinit()
        time.sleep_ms(100)
        mic.init()
        last_reset = time.ticks_ms()

    imga = mic.get_map()
    sound = mic.get_dir(imga)
    print(sound)
    mic.set_led(sound,(0,0,255))

    imgb = imga.resize(160,160)
    imgc = imgb.to_rainbow(1)
    lcd.display(imgc)

    # -------- promedio de sonido --------

    x = 0
    y = 0
    energy = 0

    for i,v in enumerate(sound):

        if v < threshold:
            continue

        angle = 2*math.pi*i/12

        x += v * math.cos(angle)
        y += v * math.sin(angle)

        energy += v

    # -------- memoria acústica --------

    memory_x *= memory_decay
    memory_y *= memory_decay

    memory_x += x
    memory_y += y

    print(memory_x)
    print(memory_y)

    # -------- determinar dirección --------
    print("energy:", energy)
    if energy > 0:

        angle = math.atan2(memory_y, memory_x)

        if angle < 0:
            angle += 2*math.pi

    else:

        explore_angle += explore_speed
        angle = explore_angle

    # -------- mapear a servos --------

    sector_size = 2*math.pi/6

    for i in range(6):

        center = i * sector_size

        diff = abs(angle - center)

        diff = min(diff, 2*math.pi - diff)

        intensity = max(0, 1 - diff/sector_size)

        servo_targets[i] = 10 + 110 * intensity

    # -------- movimiento orgánico --------
    now = time.ticks_ms()

    for i in range(6):

        # Si esta bloqueado, no aceptar nuevas órdenes
        #if servo_blocked[i]:

            # mantener en 0
            #servos.position(i, 0)

            # liberar después del tiempo
            #if time.ticks_diff(now, servo_release_time[i]) > 0:
                #servo_blocked[i] = False

            #continue

        # movimiento normal
        servo_angles[i] = servo_angles[i]*(1-alpha) + servo_targets[i]*alpha
        #print("servo")
        #print(i)
        #print(servo_angles[i])
        # condición de disparo
        if servo_angles[i] > 109:
            servo_angles[i] = 1

            #servo_blocked[i] = True
            #servo_release_time[i] = time.ticks_add(now, RETORNO_MS)

        servos.position(i, servo_angles[i])

    time.sleep_ms(80)
