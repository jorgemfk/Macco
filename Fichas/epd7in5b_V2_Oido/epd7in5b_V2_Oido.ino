#include "DEV_Config.h"
#include "EPD.h"
#include "GUI_Paint.h"
#include "imagedata.h"
#include <stdlib.h>

UBYTE *BlackImage, *RYImage;

// ----------- NEGRITAS SIMULADAS -----------
void drawBold(int x, int y, const char *text, sFONT* font) {
  Paint_DrawString_EN(x, y, text, font, WHITE, BLACK);
  Paint_DrawString_EN(x + 1, y, text, font, WHITE, BLACK);
}

// ----------- LAYOUT COMPLETO -----------
void draw_text_all() {

  Paint_SelectImage(BlackImage);
  Paint_Clear(WHITE);

  Paint_SelectImage(RYImage);
  Paint_Clear(WHITE);

  int x = 10;
  int y = 10;
  int lh20 = 22;
  int lh16 = 18;

  // ===== TITULO =====
  Paint_SelectImage(BlackImage);
  drawBold(x, y, "Hablame (Oido: coreografia orientada)", &Font24);
  y += 30;

  // ===== FICHA =====
  Paint_DrawString_EN(x, y, "Componentes electronicos, servomotores,", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "placas ceramicas y mdf", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "2026 - Coleccion del artista", &Font16, WHITE, BLACK);
  y += lh16 + 4;

  // ===== LINEA ROJA =====
  Paint_SelectImage(RYImage);
  Paint_DrawLine(x, y, 790, y, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
  y += 6;

  // ===== ESPAÑOL =====
  Paint_SelectImage(BlackImage);

  drawBold(x, y, "Un arreglo circular de microfonos detecta la direccion", &Font20);
  y += lh20;
  drawBold(x, y, "del sonido en el espacio.", &Font20);
  y += lh20;

  drawBold(x, y, "La voz no se registra: se localiza.", &Font20);
  y += lh20;

  drawBold(x, y, "Cada variacion activa un sistema de flores de ceramica", &Font20);
  y += lh20;
  drawBold(x, y, "que se abren o contraen segun la intensidad", &Font20);
  y += lh20;
  drawBold(x, y, "y procedencia de la senal.", &Font20);
  y += lh20;

  drawBold(x, y, "Escuchar aqui no es comprender, sino orientarse: una", &Font20);
  y += lh20;
  drawBold(x, y, "coreografia donde el sonido se convierte en direccion.", &Font20);
  y += lh20 + 6;

  // ===== LINEA ROJA =====
  Paint_SelectImage(RYImage);
  Paint_DrawLine(x, y, 790, y, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
  y += 6;

  // ===== INGLES =====
  Paint_SelectImage(BlackImage);

  Paint_DrawString_EN(x, y, "A circular array of microphones detects the direction", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "of sound in space.", &Font16, WHITE, BLACK);
  y += lh16;

  Paint_DrawString_EN(x, y, "The voice is not recorded - it is localized.", &Font16, WHITE, BLACK);
  y += lh16;

  Paint_DrawString_EN(x, y, "Each variation activates a system of ceramic \"flowers\"", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "that open or contract according to the intensity", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "and origin of the signal.", &Font16, WHITE, BLACK);
  y += lh16;

  Paint_DrawString_EN(x, y, "Listening here is not about understanding,", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "but about orienting: a choreography where sound", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "becomes direction.", &Font16, WHITE, BLACK);
}

// ----------- SETUP -----------
void setup() {

  DEV_Module_Init();

  UWORD Imagesize = ((EPD_7IN5B_V2_WIDTH % 8 == 0) ?
    (EPD_7IN5B_V2_WIDTH / 8) :
    (EPD_7IN5B_V2_WIDTH / 8 + 1)) * EPD_7IN5B_V2_HEIGHT;

  BlackImage = (UBYTE *)malloc(Imagesize);
  RYImage    = (UBYTE *)malloc(Imagesize);

  if (BlackImage == NULL || RYImage == NULL) {
    while (1);
  }

  Paint_NewImage(BlackImage, EPD_7IN5B_V2_WIDTH, EPD_7IN5B_V2_HEIGHT, 0, WHITE);
  Paint_NewImage(RYImage,    EPD_7IN5B_V2_WIDTH, EPD_7IN5B_V2_HEIGHT, 0, WHITE);

  Paint_SetScale(2);
}

// ----------- LOOP -----------
void loop() {

  // ===== IMAGEN =====
  EPD_7IN5B_V2_Init_Fast();
  EPD_7IN5B_V2_Display(gImage_7in5_V2_b, gImage_7in5_V2_ry);
  DEV_Delay_ms(5000);

  // ===== TEXTO =====
  EPD_7IN5B_V2_Init();
  draw_text_all();
  EPD_7IN5B_V2_Display(BlackImage, RYImage);

  DEV_Delay_ms(30000);
}