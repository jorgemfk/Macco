#include <Wire.h>
#include <U8g2lib.h>

// Lectura RAW del sensor MQ135 en Arduino Uno

const int MQ135_PIN = 39;      // Pin analógico donde está conectado el sensor
const int NUM_LECTURAS_MQ135 = 100;  // Para promediar lecturas y reducir ruido


#define MQ3_PIN 34
#define CALIBRACIONES 1000   // muestras para calibrar

U8G2_SSD1309_128X64_NONAME0_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);

float filtro = 0;
float base = 0;   // valor de MQ-3 en aire limpio

void calibrarSensor() {
  Serial.println("Calibrando MQ-3 (25 segundos)...");
  long suma = 0;

  for (int i = 0; i < CALIBRACIONES; i++) {
    suma += analogRead(MQ3_PIN);
    delay(25);
  }

  base = suma / CALIBRACIONES;
  Serial.print("Base calibrada = ");
  Serial.println(base);
}

float leerAlcoholPct() {
  int raw = analogRead(MQ3_PIN);
  Serial.println(raw);

  filtro = 0.90 * filtro + 0.10 * raw;

  float pct = (filtro - base) / (4095.0 - base) * 100.0;
  Serial.println(pct);
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  
  return pct;
}

float estimarMgL(float pct) {
  
  return pct * 0.006; // mg/L aproximado
}

void setup() {
  Serial.begin(115200);

  Wire.begin(21, 22);
  u8g2.begin();
  u8g2.setContrast(255);
  //
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tf);
  u8g2.drawStr(0, 10, "Calibrando MQ3...");
  u8g2.sendBuffer();
  calibrarSensor(); // <-- NUEVO

}

void loop() {
  float pct = leerAlcoholPct();
  float mgL = estimarMgL(pct);
  String estado = (mgL > 0.039) ? "NO CONDUCIR" : "PERMITIDO";

  //MQ135
    long suma_135 = 0;

  // Promediar para suavizar ruido
  for(int i = 0; i < NUM_LECTURAS_MQ135; i++) {
    suma_135 += analogRead(MQ135_PIN);
    delay(5);
  }

  int rawValue = suma_135 / NUM_LECTURAS_MQ135;

  // Imprimir RAW
  Serial.print("RAW MQ135: ");
  Serial.println(rawValue);
  // OLED
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tf);
  char l0[32];
  sprintf(l0, "Calidad: %d ", rawValue);
  u8g2.drawStr(0, 10, l0);

  char l1[32];
  sprintf(l1, "Alcohol: %.1f %%", pct);
  u8g2.drawStr(0, 25, l1);

  char l2[32];
  sprintf(l2, "Aire: %.3f mg/L", mgL);
  u8g2.drawStr(0, 40, l2);

  u8g2.setFont(u8g2_font_7x14B_tf);
  u8g2.drawStr(0, 60, estado.c_str());
  u8g2.sendBuffer();

  // Serial Debug
  Serial.print("RAW filtrado: ");
  Serial.print(filtro);
  Serial.print(" | Base: ");
  Serial.print(base);
  Serial.print(" | % alcohol: ");
  Serial.print(pct);
  Serial.print(" | mg/L: ");
  Serial.println(mgL,3);

  delay(200);
}
