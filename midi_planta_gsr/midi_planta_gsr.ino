// ==========================================
// PLANT MUSIC SYNTH
// Arduino Nano + GSR + LM386
// ==========================================

const int sensorPin = A1;
const int audioPin  = 9;

// filtro
float filtered = 0;
float alpha = 0.03;

// lectura previa
float lastFiltered = 0;

// escala pentatónica (suena bien casi siempre)
int scale[] = {
  131, // C3
  147, // D3
  165, // E3
  196, // G3
  220, // A3
  262, // C4
  294, // D4
  330, // E4
  392, // G4
  440  // A4
};

int scaleSize = 10;

unsigned long lastNoteTime = 0;
int currentFreq = 220;

void setup() {

  Serial.begin(115200);

  pinMode(audioPin, OUTPUT);

  Serial.println("=== PLANT MUSIC START ===");
}

void loop() {

  // leer sensor
  int raw = analogRead(sensorPin);

  // suavizar
  filtered = alpha * raw + (1.0 - alpha) * filtered;

  // detectar cambio
  float diff = abs(filtered - lastFiltered);

  // mapear sensibilidad
  int index = map(diff * 100, 0, 50, 0, scaleSize - 1);

  index = constrain(index, 0, scaleSize - 1);

  // seleccionar nota
  currentFreq = scale[index];

  // vibrato suave usando millis
  int vibrato =
    sin(millis() * 0.01) * 5;

  tone(audioPin, currentFreq + vibrato);

  // LOGS
  Serial.print("RAW: ");
  Serial.print(raw);

  Serial.print(" | FILTERED: ");
  Serial.print(filtered);

  Serial.print(" | DIFF: ");
  Serial.print(diff);

  Serial.print(" | NOTE: ");
  Serial.println(currentFreq);

  lastFiltered = filtered;

  delay(30);
}