#include <Wire.h>
#include <U8g2lib.h>
#include <ESP32Servo.h>
#include <WiFi.h>
#include <HTTPClient.h>

// =======================
// ====== SERVO CONFIG ===
// =======================
#define SERVO_360_PIN 26   // servo continuo 360
#define SERVO_180_PIN 25   // servo posicional 180

Servo servo360;
Servo servo180;

// Servo 360 (continuo)
const int SERVO360_MIN_US  = 500;
const int SERVO360_MAX_US  = 2500;
const int SERVO360_STOP_US = 1500;

// Servo 180 (posicional)
const int SERVO180_MIN_DEG = 0;
const int SERVO180_MAX_DEG = 180;
const int SERVO180_HOME    = 90;

// Estado de movimiento
int estadoServoPrev = 0;      // último estado activo (1 o 2)
bool servoActivo = false;     // si está corriendo animación
unsigned long servoInicioMs = 0;
const unsigned long DURACION_SERVO_MS = 15000; // 5 segundos

// WIFI CONFIG
const char* ssid = "JORGEMFK";

const char* serverUrl = "http://192.168.0.82:5823/olfato";

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
// nivel lectura
// ------------------------------
String nivelRaw(int raw) {
  if (raw < 1200) return "bajo";
  if (raw < 2200) return "medio";
  return "alto";
}

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
// ===== SERVO HELPERS ===
// =======================

// detener servo 360
void detenerServo360() {
  servo360.writeMicroseconds(SERVO360_STOP_US);
}

// posición home del servo 180
void homeServo180() {
  servo180.write(SERVO180_HOME);
}

// detener todo
void detenerServos() {
  detenerServo360();
  homeServo180();
}

// iniciar animación de 5 segundos
void iniciarMovimiento(int estadoServo) {
  if (estadoServo < 1 || estadoServo > 2) return;

  servoActivo = true;
  servoInicioMs = millis();
  estadoServoPrev = estadoServo;

  Serial.print("Iniciando movimiento 5s, estado = ");
  Serial.println(estadoServo);
}

// animación no bloqueante de ambos servos
void actualizarServos() {
  if (!servoActivo) {
    detenerServos();
    return;
  }

  unsigned long ahora = millis();
  unsigned long t = ahora - servoInicioMs;

  // terminar a los 5 segundos
  if (t >= DURACION_SERVO_MS) {
    servoActivo = false;
    detenerServos();
    Serial.println("Movimiento terminado (5s)");
    return;
  }

  // -----------------------------
  // SERVO 360 (pin 26)
  // -----------------------------
  // Rampa de aceleración en los primeros 1500ms
  float factor = 1.0;
  const unsigned long RAMPA_MS = 1500;

  if (t < RAMPA_MS) {
    factor = (float)t / (float)RAMPA_MS;
  }

  int offsetMax = 0;
  int direccion = 0;

  if (estadoServoPrev == 1) {
    // estado 1 = más agresivo, sentido 1
    offsetMax = 320;   // velocidad máxima
    direccion = +1;    // un sentido
  } else if (estadoServoPrev == 2) {
    // estado 2 = más suave, sentido contrario
    offsetMax = 180;   // velocidad menor
    direccion = -1;    // sentido contrario
  }

  int offsetActual = (int)(offsetMax * factor);
  int us360 = SERVO360_STOP_US + (direccion * offsetActual);
  us360 = constrain(us360, SERVO360_MIN_US, SERVO360_MAX_US);
  servo360.writeMicroseconds(us360);

  // -----------------------------
  // SERVO 180 (pin 25)
  // -----------------------------
  // movimiento tipo "torcedura" con seno
  // estado 1 y 2 tienen diferente amplitud y número de ciclos
  float progreso = (float)t / (float)DURACION_SERVO_MS; // 0.0 a 1.0

  float ciclos = 0.0;
  int centro = 90;
  int amplitud = 0;

  if (estadoServoPrev == 1) {
    // 4 torceduras medianas
    ciclos = 4.0;
    centro = 90;
    amplitud = 40; // 50 a 130 aprox
  } else if (estadoServoPrev == 2) {
    // 2 torceduras amplias
    ciclos = 2.0;
    centro = 90;
    amplitud = 70; // 20 a 160 aprox
  }

  // curva seno
  float ang = centro + amplitud * sin(2.0 * PI * ciclos * progreso);

  // pequeña "entrada" suave en los primeros 300 ms
  if (t < 300) {
    float entrada = (float)t / 300.0;
    ang = SERVO180_HOME + (ang - SERVO180_HOME) * entrada;
  }

  int angulo180 = constrain((int)ang, SERVO180_MIN_DEG, SERVO180_MAX_DEG);
  servo180.write(angulo180);

  // debug
  Serial.print("t=");
  Serial.print(t);
  Serial.print(" | estado=");
  Serial.print(estadoServoPrev);
  Serial.print(" | us360=");
  Serial.print(us360);
  Serial.print(" | ang180=");
  Serial.println(angulo180);
}

// =======================
// ======== SETUP ========
// =======================
void setup() {
  Serial.begin(115200);

  // ---- Configurar servos correctamente ----
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);

  // Servo 360
  servo360.setPeriodHertz(50);
  servo360.attach(SERVO_360_PIN, SERVO360_MIN_US, SERVO360_MAX_US);

  // Servo 180
  servo180.setPeriodHertz(50);
  servo180.attach(SERVO_180_PIN, 500, 2500);

  // posiciones iniciales
  detenerServos();

  Wire.begin(21, 22);
  u8g2.begin();

  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tf);
  u8g2.drawStr(0, 10, "Conectando...");
  u8g2.sendBuffer();

  WiFi.begin(ssid, password);

  int intentos = 0;
  while (WiFi.status() != WL_CONNECTED && intentos < 30) {
    delay(500);
    Serial.print(".");
    intentos++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi conectado");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_6x12_tf);
    u8g2.drawStr(0, 10, "WiFi conectado");
    u8g2.sendBuffer();
    delay(1000);
  } else {
    Serial.println("\nNo se pudo conectar a WiFi");
  }

  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tf);
  u8g2.drawStr(0, 10, "Calibrando...");
  u8g2.sendBuffer();

  delay(5000);
  calibrarMQ3();
  calibrarMQ135();

  Serial.println("Setup completo");
}

// =======================
// ========= LOOP ========
// =======================
void loop() {

  // ---------------- MQ3 ----------------
  float pct = leerAlcoholPct();
  float mgL = estimarMgL(pct);
  String estado = (mgL > 0.039) ? "NO CONDUCIR" : "NIVEL BAJO";

  // ---------------- MQ135 ----------------
  long suma135 = 0;
  for (int i = 0; i < NUM_LECTURAS_MQ135; i++) {
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

  // ---------------- ACTIVAR MOVIMIENTO ----------------
  // Solo dispara si detecta evento y no está ya corriendo
  if (!servoActivo && estadoServo >= 1) {
    iniciarMovimiento(estadoServo);
  }

  // actualizar animación de servos
  actualizarServos();

  // ---------------- ENVIO DATA ----------------
  String nivel = nivelRaw(raw135);

  if (WiFi.status() == WL_CONNECTED && estadoServo >= 1) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    String payload = "{";
    payload += "\"sentido\":\"olfato\",";
    payload += "\"raw135\":" + String(raw135) + ",";
    payload += "\"velocidad\":\"" + String(estadoServo) + "\",";
    payload += "\"nivel\":\"" + nivel + "\"";
    payload += "}";

    int httpResponseCode = http.POST(payload);

    if (httpResponseCode > 0) {
      Serial.print("POST enviado, codigo HTTP: ");
      Serial.println(httpResponseCode);

      String response = http.getString();
      Serial.print("Respuesta servidor: ");
      Serial.println(response);
    } else {
      Serial.print("No se puede conectar al host. Error: ");
      Serial.println(http.errorToString(httpResponseCode));
    }

    http.end();
  } else if (estadoServo >= 1) {
    Serial.println("No se puede conectar al host: WiFi no conectado");
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
  Serial.print(delta);
  Serial.print(" estadoServo=");
  Serial.print(estadoServo);
  Serial.print(" activo=");
  Serial.println(servoActivo ? "SI" : "NO");

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

  delay(80);
}