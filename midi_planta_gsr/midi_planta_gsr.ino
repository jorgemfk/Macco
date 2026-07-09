// MushroomMusicDisplay.ino  (v2 - display desacoplado del muestreo)
// Requiere: Servo, U8g2
//
// FIX PRINCIPAL:
// El dibujo en el display (firstPage/nextPage) tarda varios ms por
// cuadro. Si se llama en CADA vuelta del loop (cada 20ms nominales),
// el loop real termina tardando mucho mas que eso, y el filtro rapido
// del sensor deja de muestrear al ritmo que fue diseñado -> se pierde
// sensibilidad a cambios pequeños (menos variedad de notas, menos
// movimiento de servo).
//
// Ahora el sensor/servo/audio se actualizan CADA loop (rapido, ~20ms),
// y el display se refresca solo cada DISPLAY_INTERVAL_MS con su propio
// temporizador, sin bloquear el resto.

#include <Servo.h>
#include <Wire.h>
#include <U8g2lib.h>

const int sensorPin=A1,audioPin=9,servoPin=6;
Servo aguja;
U8G2_SH1107_128X128_2_HW_I2C display(U8G2_R2, U8X8_PIN_NONE);

enum Estado{CALIBRANDO,ESTABLE};
Estado estado=CALIBRANDO;
unsigned long estableDesde=0;
const float UMBRAL_ESTABLE=3.0;
const unsigned long TIEMPO_ESTABLE_REQUERIDO=1500;

float filtered=0,alphaFast=0.05,baseline=0;
const float alphaBaseCalib=0.02,alphaBaseStable=0.0008;
bool baselineInit=false;
float noiseFloor=1,alphaNoise=0.002,maxDev=5;
const float NOISE_MIN=0.5,NOISE_IGNORE_FACTOR=4.0;
const float DECAY_MAXDEV=0.999,MAXDEV_MIN=2.0;

// Escala para el modo HUMANO-HONGO (toques): pentatonica menor, respuesta directa a la actividad
const int escalaHumano[]={131,147,165,196,220,262,294,330,392,440,523,587,659,784,880};
const int NUM_NOTAS_HUMANO=sizeof(escalaHumano)/sizeof(int);

// Escala para el modo SOLO HONGO (sin contacto humano): mayor/lidia, registro mas agudo,
// pensada para sonar melodica y en constante deriva aunque casi no haya actividad.
const int escalaHongo[]={262,294,330,349,392,440,494,523,587,659,698,784,880,988,1047};
const int NUM_NOTAS_HONGO=sizeof(escalaHongo)/sizeof(int);

unsigned long ultimoCambioNota=0;
const unsigned long MS_ENTRE_NOTAS_HUMANO=60;   // reactivo, sigue el toque de cerca
const unsigned long MS_ENTRE_NOTAS_HONGO=220;   // mas lento y fraseado, mas "melodico"
int notaActual=440;

// --- Refresco del display desacoplado ---
unsigned long ultimoDisplay=0;
const unsigned long DISPLAY_INTERVAL_MS=150; // ajustable: mas alto = display mas lento pero sensor mas fino
int rawParaDisplay=0; // ultimo raw leido, usado solo para pintar

// --- Barra RAW: 30% mas chica que el original en ancho Y alto (120x8 -> 84x6) ---
const int BAR_X=4;
const int BAR_Y=16;
const int BAR_W=84;   // antes 120
const int BAR_H=6;    // antes 8

// --- Pixel art simple dibujado con primitivas ---
void drawHappy(){
 display.drawDisc(64,50,18);
 display.drawCircle(64,72,18);
 display.drawPixel(58,68); display.drawPixel(70,68);
 display.drawArc(64,75,8,0,180);
}
void drawAlert(){
 display.setFont(u8g2_font_logisoso32_tf);
 display.drawStr(48,52,"?");
 display.drawCircle(64,88,18);
 display.drawLine(64,70,64,40);
}
void drawLink(){
 display.drawCircle(34,48,10);
 display.drawLine(34,58,34,78);
 display.drawLine(34,64,24,72);
 display.drawLine(34,64,44,72);
 display.drawLine(34,78,24,92);
 display.drawLine(34,78,44,92);
 display.drawCircle(92,58,16);
 display.drawLine(44,64,76,60);
 display.drawDisc(60,62,2);
}
void updateDisplay(int raw){
 display.firstPage();
 do{
   // dibujos

   display.setFont(u8g2_font_6x10_tf);
   display.setCursor(0,10); display.print("RAW: "); display.print(raw);

   int b=map(raw,0,1023,0,BAR_W-2);
   display.drawFrame(BAR_X,BAR_Y,BAR_W,BAR_H);
   display.drawBox(BAR_X+1,BAR_Y+1,b,BAR_H-2);

   if(raw==0){ drawAlert(); display.drawStr(24,124,"HONGO ALERTA");}
   else if(raw<700){ drawLink(); display.drawStr(12,124,"ENLACE HUMANO-HONGO");}
   else { drawHappy(); display.drawStr(28,124,"SOLO HONGO");}
 }while(display.nextPage());
}

void setup(){
 Serial.begin(115200);
 aguja.attach(servoPin);
 display.begin();
 int r=analogRead(sensorPin);
 filtered=baseline=r;
 baselineInit=true;
}

void loop(){
 // ------------------------
 // SENSOR / AUDIO / SERVO: cada vuelta del loop (~20ms), sin bloqueos
 // ------------------------
 int raw=analogRead(sensorPin);
 rawParaDisplay=raw;

 filtered=alphaFast*raw+(1-alphaFast)*filtered;
 float a=(estado==CALIBRANDO)?alphaBaseCalib:alphaBaseStable;
 baseline=a*filtered+(1-a)*baseline;
 float dev=filtered-baseline;
 float absDev=fabs(dev);

 if(estado==CALIBRANDO){
   if(absDev<UMBRAL_ESTABLE){
    if(!estableDesde)estableDesde=millis();
    if(millis()-estableDesde>TIEMPO_ESTABLE_REQUERIDO){estado=ESTABLE;noiseFloor=max(absDev,NOISE_MIN);maxDev=MAXDEV_MIN;}
   } else estableDesde=0;
 } else if(absDev>maxDev*6&&absDev>40){estado=CALIBRANDO;estableDesde=0;}

 if(estado==ESTABLE){
  if(absDev<noiseFloor*NOISE_IGNORE_FACTOR)noiseFloor=alphaNoise*absDev+(1-alphaNoise)*noiseFloor;
  if(noiseFloor<NOISE_MIN)noiseFloor=NOISE_MIN;
  maxDev*=DECAY_MAXDEV; if(absDev>maxDev)maxDev=absDev; if(maxDev<MAXDEV_MIN)maxDev=MAXDEV_MIN;
 }

 aguja.write(estado==CALIBRANDO?90:constrain((int)(90+(dev/maxDev)*90),0,180));

 if(raw==0){
   // Sensor desconectado / sin señal: silencio total, sin importar el estado
   noTone(audioPin);

 } else if(estado==ESTABLE && raw<700){
   // ------------------------
   // MODO HUMANO-HONGO: reactivo al toque, escala pentatonica menor
   // ------------------------
   int idx=constrain(map((int)(absDev*100/maxDev),0,100,0,NUM_NOTAS_HUMANO-1),0,NUM_NOTAS_HUMANO-1);
   if(millis()-ultimoCambioNota>MS_ENTRE_NOTAS_HUMANO){
     notaActual=escalaHumano[idx];
     ultimoCambioNota=millis();
   }
   int vibrato=(int)(sin(millis()*0.01)*8);
   tone(audioPin,notaActual+vibrato);

 } else if(estado==ESTABLE && raw>=700){
   // ------------------------
   // MODO SOLO HONGO: escala distinta (mayor/lidia, mas aguda) y con
   // deriva melodica propia en el tiempo, para que suene vivo y variado
   // aunque el hongo este quieto (sin depender solo de la actividad).
   // ------------------------
   unsigned long t=millis();
   float drift = ( sin(t*0.0007) + sin(t*0.00033+1.7) + sin(t*0.00151+0.4) ) / 3.0; // -1..1 suave
   int idxDrift = (int)((drift*0.5+0.5)*(NUM_NOTAS_HONGO-1));

   // pequeño empujon extra si hay algo de actividad real, sin que domine
   int idxActividad = (int)(absDev/noiseFloor);
   int idx = constrain(idxDrift + idxActividad, 0, NUM_NOTAS_HONGO-1);

   if(millis()-ultimoCambioNota>MS_ENTRE_NOTAS_HONGO){
     notaActual=escalaHongo[idx];
     ultimoCambioNota=millis();
   }
   int vibrato=(int)(sin(t*0.003)*15); // vibrato mas ancho y lento, timbre distinto
   tone(audioPin,notaActual+vibrato);

 } else {
   noTone(audioPin); // CALIBRANDO
 }

 // ------------------------
 // DISPLAY: solo cada DISPLAY_INTERVAL_MS, no en cada vuelta
 // ------------------------
 if(millis()-ultimoDisplay>DISPLAY_INTERVAL_MS){
   updateDisplay(rawParaDisplay);
   ultimoDisplay=millis();
 }

 delay(20);
}