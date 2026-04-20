#include "DEV_Config.h"
#include "EPD.h"
#include "GUI_Paint.h"
#include "fonts.h"
#include "ImageData.h"

UBYTE *BlackImage;
UBYTE *RYImage;

// ----------- NEGRITAS -----------
void drawBold(int x, int y, const char *text, sFONT* font) {
    Paint_DrawString_EN(x, y, text, font,  WHITE, BLACK);
    Paint_DrawString_EN(x+1, y, text, font,  WHITE, BLACK);
}

// ----------- ESPAÑOL -----------
void draw_spanish() {

    // limpiar ambos buffers
    Paint_SelectImage(BlackImage);
    Paint_Clear(WHITE);
    Paint_SelectImage(RYImage);
    Paint_Clear(WHITE);

    int x = 10;
    int y = 10;
    int lh = 22;

    // ===== NEGRO =====
    Paint_SelectImage(BlackImage);

    drawBold(x, y, "Mirame 2.0 (Vista: espejo emocional)", &Font16);
    y += 22;

    Paint_DrawString_EN(x, y, "Componentes electronicos, servomotores,", &Font12,  WHITE, BLACK);
    y += 14;
    Paint_DrawString_EN(x, y, "lino, lana tenido con anil y algodon natural", &Font12,  WHITE, BLACK);
    y += 14;
    Paint_DrawString_EN(x, y, "2026 - Coleccion del artista", &Font12,  WHITE, BLACK);
    y += 18;

    // ===== ROJO =====
    Paint_SelectImage(RYImage);
    Paint_DrawLine(x, y, 390, y, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
    y += 8;

    // ===== TEXTO NEGRO =====
    Paint_SelectImage(BlackImage);

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

    Paint_SelectImage(BlackImage);
    Paint_Clear(WHITE);
    Paint_SelectImage(RYImage);
    Paint_Clear(WHITE);

    int x = 10;
    int y = 20;
    int lh = 18;

    Paint_SelectImage(BlackImage);

    drawBold(x, y, "Look at me", &Font20);
    y += 24;

    Paint_DrawString_EN(x, y, "An artificial vision system ", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "recognizes human faces and ", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "classifies emotions to ", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "activate movements and ", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "deformations in the textile", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, " surface. The machine does ", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "not see images—it interprets", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, " patterns. What it returns ", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "is not a faithful reflection", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, ", but a coded affective  ", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "response. Vision shifts ", &Font16,  WHITE, BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "from recognition to inference.", &Font16,  WHITE, BLACK);
}

void setup() {

    printf("EPD_4IN2B_V2 Demo\r\n");
    DEV_Module_Init();

    EPD_4IN2B_V2_Init();
    EPD_4IN2B_V2_Clear();
    DEV_Delay_ms(1000);

    UWORD Imagesize = ((EPD_4IN2B_V2_WIDTH % 8 == 0) ?
        (EPD_4IN2B_V2_WIDTH / 8) :
        (EPD_4IN2B_V2_WIDTH / 8 + 1)) * EPD_4IN2B_V2_HEIGHT;

    BlackImage = (UBYTE *)malloc(Imagesize);
    RYImage = (UBYTE *)malloc(Imagesize);

    Paint_NewImage(BlackImage, EPD_4IN2B_V2_WIDTH, EPD_4IN2B_V2_HEIGHT, 0, WHITE);
    Paint_NewImage(RYImage, EPD_4IN2B_V2_WIDTH, EPD_4IN2B_V2_HEIGHT, 0, WHITE);
}

void loop() {

    // ===== IMAGEN FULL =====
    //EPD_4IN2B_V2_Display(gImage_4in2bc_b, gImage_4in2bc_ry);
    DEV_Delay_ms(4000);

    // ===== ESPAÑOL =====
    draw_spanish();
    EPD_4IN2B_V2_Display(BlackImage, RYImage);
    DEV_Delay_ms(20000);

    // ===== INGLES =====
    draw_english();
    EPD_4IN2B_V2_Display(BlackImage, RYImage);
    DEV_Delay_ms(20000);
}