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
  drawBold(x, y, "Tocame en las antenas negras (cuerpo evasivo)", &Font24);
  y += 33;

  // ===== FICHA =====
  Paint_DrawString_EN(x, y, "Componentes electronicos, servomotores,", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "lana tenido con anil y algodon natural", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "2026 - Coleccion del artista", &Font16, WHITE, BLACK);
  y += lh16 + 4;

  // ===== LINEA ROJA =====
  Paint_SelectImage(RYImage);
  Paint_DrawLine(x, y, 790, y, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
  y += 6;

  // ===== ESPAÑOL =====
  Paint_SelectImage(BlackImage);

  drawBold(x, y, "La pieza permanece en reposo hasta ser tocada.", &Font20);
  y += lh20;

  drawBold(x, y, "Ante el contacto, activa un desplazamiento que busca", &Font20);
  y += lh20;
  drawBold(x, y, "alejarse del estimulo.", &Font20);
  y += lh20;

  drawBold(x, y, "El tacto no genera proximidad, sino distancia.", &Font20);
  y += lh20;

  drawBold(x, y, "Aqui, sentir implica reaccionar: un cuerpo que no", &Font20);
  y += lh20;
  drawBold(x, y, "se deja poseer, que traduce el contacto en huida.", &Font20);
  y += lh20 + 6;

  // ===== LINEA ROJA =====
  Paint_SelectImage(RYImage);
  Paint_DrawLine(x, y, 790, y, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
  y += 6;

  // ===== INGLES =====
  Paint_SelectImage(BlackImage);

  Paint_DrawString_EN(x, y, "The piece remains at rest until it is touched.", &Font16, WHITE, BLACK);
  y += lh16;

  Paint_DrawString_EN(x, y, "Upon contact, it activates a movement that seeks", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "to move away from the stimulus.", &Font16, WHITE, BLACK);
  y += lh16;

  Paint_DrawString_EN(x, y, "Touch does not generate proximity, but distance.", &Font16, WHITE, BLACK);
  y += lh16;

  Paint_DrawString_EN(x, y, "Here, sensing implies reacting: a body that resists", &Font16, WHITE, BLACK);
  y += lh16;
  Paint_DrawString_EN(x, y, "being held, translating contact into escape.", &Font16, WHITE, BLACK);
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