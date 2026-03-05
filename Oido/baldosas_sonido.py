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

    def freq(self, freq=None):
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

    def duty(self, index, value=None):
        if value is None:
            pwm = self.pwm(index)
            return pwm[1]
        self.pwm(index, 0, value)

class Servos:
    def __init__(self, i2c, address=0x40, freq=50, min_us=500, max_us=2500, degrees=180):
        self.period = 1000000 / freq
        self.min_duty = int(4095 * min_us / self.period)
        self.max_duty = int(4095 * max_us / self.period)
        self.degrees = degrees
        self.pca9685 = PCA9685(i2c, address)
        self.pca9685.freq(freq)

    def position(self, index, degrees):
        span = self.max_duty - self.min_duty
        duty = self.min_duty + span * degrees / self.degrees
        duty = min(self.max_duty, max(self.min_duty, int(duty)))
        self.pca9685.duty(index, duty)

# ---------------- I2C y servos ----------------

i2c1 = I2C(I2C.I2C0, mode=I2C.MODE_MASTER, scl=7, sda=6)
s = Servos(i2c1)

# ---------------- LOOP PRINCIPAL ----------------

while True:

    imga = mic.get_map()
    sound = mic.get_dir(imga)

    print(sound)

    # visualización
    mic.set_led(sound, (0,0,255))
    imgb = imga.resize(160,160)
    imgc = imgb.to_rainbow(1)
    lcd.display(imgc)

    # controlar servos
    for servo in range(6):

        i1 = servo * 2
        i2 = servo * 2 + 1

        intensidad = sound[i1] + sound[i2]

        angulo = 120 * intensidad / 30

        s.position(servo, angulo)

    time.sleep_ms(50)
