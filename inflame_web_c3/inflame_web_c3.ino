#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <DNSServer.h>
#include <ESP32Servo.h>

const byte DNS_PORT = 53;
DNSServer dnsServer;
Servo myservo;

const char* ssid = "Inflame";
const int MAX_CLIENTES = 5;
AsyncWebServer server(80);
IPAddress apIP(192, 168, 4, 1);

unsigned long infladas = 0;
/*
#define COUNT_LOW 1638
#define COUNT_HIGH 7864

void ledcAnalogWrite(uint8_t channel, uint32_t value, uint32_t valueMax = 180) {
  if(value > valueMax) value = valueMax;
  uint32_t duty = COUNT_LOW + (((COUNT_HIGH - COUNT_LOW) / valueMax) * value);
  ledcWrite(channel, duty);
}*/

void setup() {
  Serial.begin(115200);
  myservo.attach(5);

  WiFi.softAP(ssid, "", 1, 0, MAX_CLIENTES);
  WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));

  dnsServer.start(DNS_PORT, "*", apIP);

  server.onNotFound([](AsyncWebServerRequest *request){
    request->redirect("/");
  });

  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    String html = R"rawliteral(
      <!DOCTYPE html>
      <html>
      <body align="center">
        <button style="background-color:lightgrey;width:300px;height:300px;" 
          onmousedown="getsend('infla')" 
          onmouseup="getsend('stop')" 
          ontouchstart="getsend('infla')" 
          ontouchend="getsend('stop')">
          <b>Inflame ;(</b>
        </button>
        <br><br>
        <p>Infladas: )rawliteral";
    html += String(infladas);
    html += R"rawliteral(</p>
        <script>
          function getsend(action) {
            fetch(`/${action}`).then(response => response.text());
          }
        </script>
      </body>
      </html>
    )rawliteral";
    request->send(200, "text/html", html);
  });

  server.on("/infla", HTTP_GET, [](AsyncWebServerRequest *request){
    Serial.println("Inflar");
    //ledcAnalogWrite(2, 180);
    infladas++;
    myservo.write(180);
    delay(2000); // pequeño delay no crítico
    myservo.write(0);
    delay(2000);
    //ledcAnalogWrite(2, 0);
    Serial.printf("Inflando %lu\n", infladas);
    request->send(200, "text/plain", "Infla");
  });

  server.on("/stop", HTTP_GET, [](AsyncWebServerRequest *request){
    Serial.println("Stop");
    request->send(200, "text/plain", "Stop");
  });

  server.begin();
  Serial.println("Servidor iniciado");
}

void loop() {
  dnsServer.processNextRequest();
}

