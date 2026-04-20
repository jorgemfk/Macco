#include "DEV_Config.h"
#include "EPD_4in2g.h"
#include "GUI_Paint.h"
#include "fonts.h"
#include "ImageData.h"

UBYTE *Image;

// ----------- NEGRITAS -----------
void drawBold(int x, int y, const char *text, sFONT* font) {
    Paint_DrawString_EN(x, y, text, font, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    Paint_DrawString_EN(x+1, y, text, font, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
}

// ----------- ESPAÑOL -----------
void draw_spanish() {

    Paint_SelectImage(Image);
    Paint_Clear(EPD_4IN2G_WHITE);

    int x = 10;
    int y = 10;
    int lh = 22;

    // TITULO
    drawBold(x, y, "Mirame 2.0 (Vista: espejo emocional)", &Font16);
    y += 22;

    // FICHA
    Paint_DrawString_EN(x, y, "Componentes electronicos, servomotores,", &Font12, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += 14;
    Paint_DrawString_EN(x, y, "lino, lana tenido con anil y algodon natural", &Font12, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += 14;
    Paint_DrawString_EN(x, y, "2026 - Coleccion del artista", &Font12, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += 18;

    // LINEA ROJA
    Paint_DrawLine(x, y, 390, y, EPD_4IN2G_RED, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
    y += 8;

    // TEXTO
    drawBold(x, y, "Un sistema de vision artificial ", &Font16);
    y += lh;
    drawBold(x, y, "reconoce rostros y clasifica ", &Font16);
    y += lh;
    drawBold(x, y, "emociones para activar ", &Font16);
    y += lh;
    drawBold(x, y, "movimientos y deformaciones en ", &Font16);
    y += lh;

    drawBold(x, y, "la materia textil. La maquina no", &Font16);
    y += lh;
    drawBold(x, y, " ve imagenes: interpreta patrones", &Font16);
    y += lh;
    drawBold(x, y, "Lo que devuelve no es un reflejo ", &Font16);
    y += lh;
    drawBold(x, y, "fiel, sino una respuesta afectiva ", &Font16);
    y += lh;
    drawBold(x, y, "codificada. La mirada se desplaza ", &Font16);
    y += lh;
    drawBold(x, y, "del reconocimiento a la inferencia. ", &Font16);
   
}

// ----------- INGLES -----------
void draw_english() {

    Paint_SelectImage(Image);
    Paint_Clear(EPD_4IN2G_WHITE);

    int x = 10;
    int y = 20;
    int lh = 18;
    drawBold(x, y, "Look at me", &Font20);
    y += 24;
    Paint_DrawString_EN(x, y, "An artificial vision system ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "recognizes human faces and ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "classifies emotions to ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "activate movements and ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "deformations in the textile", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, " surface. The machine does ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "not see images—it interprets", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, " patterns. What it returns ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;

    Paint_DrawString_EN(x, y, "is not a faithful reflection", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, ", but a coded affective  ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "response. Vision shifts ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "from recognition to inference.", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    
}

void setup() {

    printf("EPD_4IN2G Demo\r\n");
    DEV_Module_Init();

    EPD_4IN2G_Init();
    EPD_4IN2G_Clear(EPD_4IN2G_WHITE);
    DEV_Delay_ms(1000);

    // memoria
    UWORD Imagesize = ((EPD_4IN2G_WIDTH % 4 == 0) ?
        (EPD_4IN2G_WIDTH / 4) :
        (EPD_4IN2G_WIDTH / 4 + 1)) * EPD_4IN2G_HEIGHT;

    Image = (UBYTE *)malloc(Imagesize);

    Paint_NewImage(Image, EPD_4IN2G_WIDTH, EPD_4IN2G_HEIGHT, 0, EPD_4IN2G_WHITE);
    Paint_SetScale(4);
}

void loop() {

    // ===== IMAGEN FULL =====
    EPD_4IN2G_Display(nose);
    DEV_Delay_ms(4000);

    // ===== ESPAÑOL =====
    draw_spanish();
    EPD_4IN2G_Display(Image);
    DEV_Delay_ms(20000);

    // ===== INGLES =====
    draw_english();
    EPD_4IN2G_Display(Image);
    DEV_Delay_ms(20000);
}