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
    drawBold(x, y, "Soplame(Olfato:capullos de aliento)", &Font16);
    y += 22;

    // FICHA
    Paint_DrawString_EN(x, y, "Componentes electronicos, servomotores,", &Font12, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += 14;
    Paint_DrawString_EN(x, y, "ceramica, lana tenido con anil y algodon natural", &Font12, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += 14;
    Paint_DrawString_EN(x, y, "2026 - Coleccion del artista", &Font12, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += 18;

    // LINEA ROJA
    Paint_DrawLine(x, y, 390, y, EPD_4IN2G_RED, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
    y += 8;

    // TEXTO
    drawBold(x, y, "Variaciones en la composicion del ", &Font16);
    y += lh;
    drawBold(x, y, "aire - aliento, gases, presencia - ", &Font16);
    y += lh;
    drawBold(x, y, "son captadas y traducidas en ", &Font16);
    y += lh;
    drawBold(x, y, "movimiento.", &Font16);
    y += lh;

    drawBold(x, y, "Los capullos suspendidos responden ", &Font16);
    y += lh;
    drawBold(x, y, "a lo invisible: fluctuaciones que ", &Font16);
    y += lh;
    drawBold(x, y, "no se ven pero afectan.", &Font16);
    y += lh;
    drawBold(x, y, "Oler se convierte en detectar ", &Font16);
    y += lh;
    drawBold(x, y, "alteraciones, en hacer visible lo ", &Font16);
    y += lh;
    drawBold(x, y, "que normalmente se dispersa. ", &Font16);
   
}

// ----------- INGLES -----------
void draw_english() {

    Paint_SelectImage(Image);
    Paint_Clear(EPD_4IN2G_WHITE);

    int x = 10;
    int y = 20;
    int lh = 18;
    drawBold(x, y, "Blow me (breath cocoons)", &Font20);
    y += 24;
    Paint_DrawString_EN(x, y, "Variations in air composition - ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "breath , gases, presence - are ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "captured and translated into", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "movement.", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "The suspended cocoons respond ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "to the invisible: fluctuations", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "that cannot be seen but still ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, " affect. ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;

    Paint_DrawString_EN(x, y, "Smell becomes the detection of ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "change, a way of making ", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "perceptible what usually", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    y += lh;
    Paint_DrawString_EN(x, y, "disperses.", &Font16, EPD_4IN2G_WHITE, EPD_4IN2G_BLACK);
    
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