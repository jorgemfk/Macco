/*
   ==========================================
   PLANT MUSIC SYNTH + SERVO
   Arduino Nano
   GSR Grove -> A1
   LM386     -> D9
   Servo     -> D6
   ==========================================
*/

#include <Servo.h>

const int sensorPin = A1;
const int audioPin  = 9;
const int servoPin  = 6;

Servo aguja;

// filtro
float filtered = 0;
float alpha = 0.03;

// para detectar cambios
float lastFiltered = 0;

// rango observado
int minVal = 1023;
int maxVal = 0;

// escala pentatonica menor
const int escala[] = {
  131, // C3
  147, // D3
  165, // E3
  196, // G3
  220, // A3
  262, // C4
  294, // D4
  330, // E4
  392, // G4
  440, // A4
  523, // C5
  587, // D5
  659, // E5
  784, // G5
  880  // A5
};

const int NUM_NOTAS =
  sizeof(escala) / sizeof(escala[0]);

unsigned long ultimoCambioNota = 0;
int notaActual = 440;

void setup() {

  Serial.begin(115200);

  aguja.attach(servoPin);

  Serial.println();
}

void loop() {

  // ------------------------
  // LEER SENSOR
  // ------------------------

  int raw = analogRead(sensorPin);

  filtered =
      alpha * raw +
      (1.0 - alpha) * filtered;

  // rango dinámico observado
  if (raw < minVal) minVal = raw;
  if (raw > maxVal) maxVal = raw;

  // ------------------------
  // ACTIVIDAD
  // ------------------------

  float delta =
      fabs(filtered - lastFiltered);

  // actividad amplificada 120 default 500 alto
  float actividad = delta * 500.0;

  // ------------------------
  // SERVO
  // ------------------------

  int rango = maxVal - minVal;

  if (rango < 10)
    rango = 10;

  int angulo =
      map(filtered,
          minVal,
          maxVal,
          0,
          180);

  angulo = constrain(angulo, 0, 180);

  aguja.write(angulo);

  // ------------------------
  // MUSICA
  // ------------------------

  int indice =
      map((int)actividad,
          0,
          50,
          0,
          NUM_NOTAS - 1);

  indice =
      constrain(indice,
                0,
                NUM_NOTAS - 1);

  int nuevaNota =
      escala[indice];

  // actualizar cada 80 ms
  if (millis() - ultimoCambioNota > 80) {

    notaActual = nuevaNota;

    ultimoCambioNota = millis();
  }

  // vibrato suave
  float t = millis() * 0.01;

  int vibrato =
      (int)(sin(t) * 8);

  tone(audioPin,
       notaActual + vibrato);

  // ------------------------
  // LOGS
  // ------------------------

  Serial.print("RAW=");
  Serial.print(raw);

  Serial.print(" FILT=");
  Serial.print(filtered, 1);

  Serial.print(" DELTA=");
  Serial.print(delta, 3);

  Serial.print(" ACT=");
  Serial.print(actividad, 1);

  Serial.print(" NOTA=");
  Serial.print(notaActual);

  Serial.print(" ANG=");
  Serial.print(angulo);

  Serial.print(" MIN=");
  Serial.print(minVal);

  Serial.print(" MAX=");
  Serial.println(maxVal);

  lastFiltered = filtered;

  delay(20);
}