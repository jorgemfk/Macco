// MushroomMusicDisplay.ino
// Basado en el sketch del usuario.
// Requiere:
// Servo
// U8g2
#include <Servo.h>
#include <Wire.h>
#include <U8g2lib.h>

const int sensorPin=A1,audioPin=9,servoPin=6;
Servo aguja;
U8G2_SH1107_128X128_F_HW_I2C display(U8G2_R0,U8X8_PIN_NONE);

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

const int escala[]={131,147,165,196,220,262,294,330,392,440,523,587,659,784,880};
const int NUM_NOTAS=sizeof(escala)/sizeof(int);
unsigned long ultimoCambioNota=0;
const unsigned long MS_ENTRE_NOTAS=60;
int notaActual=440;

// --- Pixel art simple 64x64 dibujado con primitivas ---
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
 display.clearBuffer();
 display.setFont(u8g2_font_6x10_tf);
 display.setCursor(0,10); display.print("RAW: "); display.print(raw);
 int b=map(raw,0,1023,0,120);
 display.drawFrame(4,16,120,8);
 display.drawBox(5,17,b,6);
 if(raw==0){ drawAlert(); display.drawStr(24,124,"HONGO ALERTA");}
 else if(raw<700){ drawLink(); display.drawStr(12,124,"ENLACE HUMANO-HONGO");}
 else { drawHappy(); display.drawStr(28,124,"SOLO HONGO");}
 display.sendBuffer();
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
 int raw=analogRead(sensorPin);
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
 if(estado==ESTABLE){
  int idx=constrain(map((int)(absDev*100/maxDev),0,100,0,NUM_NOTAS-1),0,NUM_NOTAS-1);
  if(millis()-ultimoCambioNota>MS_ENTRE_NOTAS){notaActual=escala[idx];ultimoCambioNota=millis();}
  tone(audioPin,notaActual+(int)(sin(millis()*0.01)*8));
 } else noTone(audioPin);
 updateDisplay(raw);
 delay(20);
}
