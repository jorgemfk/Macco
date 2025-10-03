#Experiment name: Face detection
import sensor,lcd,time
import _thread
import KPU as kpu
from machine import Timer,PWM


#servo init
tim = Timer(Timer.TIMER0, Timer.CHANNEL0, mode=Timer.MODE_PWM)
tim2 = Timer(Timer.TIMER1, Timer.CHANNEL1, mode=Timer.MODE_PWM)
tim3 = Timer(Timer.TIMER2, Timer.CHANNEL2, mode=Timer.MODE_PWM)
#tim4 = Timer(Timer.TIMER2, Timer.CHANNEL3, mode=Timer.MODE_PWM)
S3 = PWM(tim3, freq=50, duty=0, pin=34)
#S4 = PWM(tim4, freq=50, duty=0, pin=33)
S1 = PWM(tim, freq=50, duty=0, pin=17)
S2 = PWM(tim2, freq=50, duty=0, pin=35)
S1.enable()
S2.enable()
S3.enable()
flag=0
rostro_detectado = False
ciclos=4
ciclos_cont=0
espera=6
espera_cont=0
def fanc(timer):
    print("Uncani")

def move_servo(timer):
    global flag
    global rostro_detectado
    global ciclos
    global ciclos_cont
    global espera
    global espera_cont
    print("S3 enable")
    flag = 50 if flag == 0 else 0
    if rostro_detectado :
        #flag = 25
        if espera_cont > espera:
            if ciclos_cont<ciclos:
                servoa(S3, flag)
                ciclos_cont+=1
            else:
                espera_cont=0
                ciclos_cont=0
        else:
            espera_cont+= 1
        #time.sleep(0.1)
        #flag=0
        #servoa(S3, flag)
        #time.sleep(0.1)
        #flag = 20
        #servoa(S3, flag)
        #flag=0
        #time.sleep(0.1)
        #servoa(S3, flag)
    else:
        print("sin rostro")
        espera_cont= espera+1
        ciclos_cont=0

    #timer.start()
#funcion agulo en servo

# Función para mapear valores (equivalente a Arduino map())
def map_value(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

# Función para mover los servos a un ángulo específico
def set_angle(servo, angle, angle_max=180):
    if angle > angle_max:
        angle = angle_max
    duty = 40 + ((115 - 40) * angle) // angle_max  # Ajuste para MaixPy PWM
    servo.duty(duty)

def servoa(servo,angle):
    servo.duty((angle+90)/180*10+2.5)
#fin servo

##Camera module initialization

time.sleep(2)
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
#sensor.set_vflip(1)    #Camera rear mode
#sensor.set_auto_gain(False)  # Ajusta automáticamente la ganancia
#sensor.set_auto_exposure(True)  # Aumenta la exposición
sensor.set_brightness(2)  # Aumenta brillo
#sensor.set_contrast(2)  # Aumenta contraste

lcd.init() #LCD initialize

clock = time.clock()

#you can save the model to the K210 flash or SD card.
#task = kpu.load(0x300000) #Need to burn the model (face.kfpkg) to the 0x300000 position of the flash
task = kpu.load("/sd/facedetect.kmodel") #put the model to the SD card

#Model description parameters
anchor = (1.889, 2.5245, 2.9465, 3.94056, 3.99987, 5.3658, 5.155437, 6.92275, 6.718375, 9.01025)

#Initialize yolo2 network
a = kpu.init_yolo2(task, 0.5, 0.3, 5, anchor)

# Iniciar un hilo para el movimiento de los servos
timer = Timer(Timer.TIMER0, Timer.CHANNEL3, mode=Timer.MODE_PERIODIC, period=300, callback=move_servo)
#conu
try:
    with open("/sd/conteo.txt", "r") as f:
        count = int(f.read())
except Exception:
    count = 0
#con
while(True):
    clock.tick()
    img = sensor.snapshot()
    code = kpu.run_yolo2(task, img) #Run yolo2 network
    cara=True
    #Draw a rectangle when the face is recognized
    if code:


        # 5. Mostrar el número en la pantalla en color verde

        for i in code:

            print("fACE {}".format( i))
            if cara:
                b = img.draw_rectangle(i.rect(),lcd.RED)
                print (i.rect())
                x,y,w,h=i.rect()
                print(w)
                print(y)
                print(h)
                print(x)
                half_width = w // 2
                half_height = h // 2

                # Centro del rostro en la imagen
                face_center_pan = x + half_width
                face_center_tilt = y + half_height

                # Convertir coordenadas a ángulos de servo
                My_centerx = map_value(face_center_pan, half_width, 320 - half_width, 0, 90)
                My_centery = map_value(face_center_tilt, half_height, 240 - half_height, 45, 0)

                print("X {}".format(My_centerx))
                print("Y {}".format(My_centery))
                # Mover servos
                servoa(S1, My_centerx)
                servoa(S2, My_centery)
                time.sleep(0.06 )
                cara = False
        if not rostro_detectado:
            print("Rostro detectado: Activando temporizador")
            rostro_detectado = True
            count += 1
            #

            with open("/sd/conteo.txt", "w") as f:
                f.write(str(count))
    else:
        if rostro_detectado:
            print("No hay rostro: Desactivando temporizador")
            rostro_detectado = False

    #LCD display
    img.draw_string(10, 5, str(count), lcd.GREEN)
    lcd.display(img)

