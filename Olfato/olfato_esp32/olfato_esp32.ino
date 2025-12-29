#include <Wire.h>
#include <U8g2lib.h>
#include <ESP32Servo.h>

// =======================
// ====== SERVO CONFIG ===
// =======================
#define SERVO_PIN 26
Servo servoCont;
int estadoServoPrev = -1; 
// 0 = Estable, 1 = Rapido +, 2 = Rapido -

// =======================
// ====== MQ135 CONFIG ====
// =======================
const int MQ135_PIN = 39;
const int NUM_LECTURAS_MQ135 = 100;
const float RLOAD = 10.0;
float R0_135 = 1.0;
const int UMBRAL_DELTA = 80;

int raw135_prev = 0;

// =======================
// ====== MQ3 CONFIG =====
// =======================
#define MQ3_PIN 34
#define CALIBRACIONES 1000

U8G2_SSD1309_128X64_NONAME0_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);

float filtro = 0;
float base = 0;

// ------------------------------
// Calibración MQ3
// ------------------------------
void calibrarMQ3() {
  long suma = 0;
  for (int i = 0; i < CALIBRACIONES; i++) {
    suma += analogRead(MQ3_PIN);
    delay(25);
  }
  base = suma / CALIBRACIONES;
}

// ------------------------------
float leerAlcoholPct() {
  int raw = analogRead(MQ3_PIN);
  filtro = 0.90 * filtro + 0.10 * raw;

  float pct = (filtro - base) / (4095.0 - base) * 100.0;

  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

float estimarMgL(float pct) {
  return pct * 0.006;
}

// ------------------------------
// MQ135: RAW → RS → mg
// ------------------------------
float calcularRS(float raw) {
  float volt = raw * (3.3 / 4095.0);
  if (volt <= 0.1) volt = 0.1;
  return (3.3 - volt) * RLOAD / volt;
}

float mg135_from_ratio(float ratio) {
  return ratio * 100.0;  
}

// ------------------------------
void calibrarMQ135() {
  long suma = 0;

  for (int i = 0; i < 200; i++) {
    suma += analogRead(MQ135_PIN);
    delay(10);
  }

  int raw = suma / 200;
  float rs = calcularRS(raw);

  R0_135 = rs / 3.6;
}

// =======================
// ======== SETUP =========
// =======================
void setup() {
  Serial.begin(115200);

  // Servo
  servoCont.attach(SERVO_PIN);
  servoCont.write(0); // posición inicial

  Wire.begin(21, 22);
  u8g2.begin();

  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tf);
  u8g2.drawStr(0, 10, "Calibrando...");
  u8g2.sendBuffer();

  calibrarMQ3();
  calibrarMQ135();
}

// =======================
// ========= LOOP =========
// =======================
void loop() {

  // ---------------- MQ3 ----------------
  float pct = leerAlcoholPct();
  float mgL = estimarMgL(pct);
  String estado = (mgL > 0.039) ? "NO CONDUCIR" : "PERMITIDO";

  // ---------------- MQ135 ----------------
  long suma135 = 0;
  for (int i=0; i < NUM_LECTURAS_MQ135; i++) {
    suma135 += analogRead(MQ135_PIN);
    delay(5);
  }

  int raw135 = suma135 / NUM_LECTURAS_MQ135;
  float rs = calcularRS(raw135);
  float ratio = rs / R0_135;
  float mg135 = mg135_from_ratio(ratio);

  int delta = raw135 - raw135_prev;
  raw135_prev = raw135;

  String nivelCont;
  int estadoServo = 0;

  if (abs(delta) > UMBRAL_DELTA) {
    if (delta > 0) {
      nivelCont = "Rapido +";
      estadoServo = 1;
    } else {
      nivelCont = "Rapido -";
      estadoServo = 2;
    }
  } else {
    nivelCont = "Estable";
    estadoServo = 0;
  }

  // ---------------- SERVO CONTROL ----------------
  if (estadoServo != estadoServoPrev) {
    if (estadoServo == 1) servoCont.write(180);
    else if (estadoServo == 2) servoCont.write(90);
    else servoCont.write(0);

    estadoServoPrev = estadoServo;
  }

  // ---------------- BARRA DE CONTAMINACIÓN ----------------
  int barWidth = map(raw135, 200, 3500, 0, 120);
  barWidth = constrain(barWidth, 0, 120);

  // ---------------- SERIAL DEBUG ----------------
  Serial.print("MQ135 RAW=");
  Serial.print(raw135);
  Serial.print(" mg135=");
  Serial.print(mg135);
  Serial.print(" delta=");
  Serial.println(delta);

  // ---------------- OLED ----------------
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tf);

  u8g2.drawFrame(0, 0, 128, 10);
  u8g2.drawBox(1, 1, barWidth, 8);

  char l1[32];
  sprintf(l1, "Nivel: %s", nivelCont.c_str());
  u8g2.drawStr(0, 22, l1);

  char l2[32];
  sprintf(l2, "Alcohol: %.1f %%", pct);
  u8g2.drawStr(0, 35, l2);

  char l3[32];
  sprintf(l3, "Aire: %.3f mg/L", mgL);
  u8g2.drawStr(0, 48, l3);

  u8g2.setFont(u8g2_font_7x14B_tf);
  u8g2.drawStr(0, 64, estado.c_str());

  u8g2.sendBuffer();

  delay(150);
}
