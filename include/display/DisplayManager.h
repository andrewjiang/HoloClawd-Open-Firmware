#pragma once

#include <Arduino.h>
#include <Arduino_GFX_Library.h>

// Colors definitions
static constexpr uint16_t LCD_BLACK = 0x0000;
static constexpr uint16_t LCD_WHITE = 0xFFFF;
static constexpr uint16_t LCD_RED = 0xF800;
static constexpr uint16_t LCD_GREEN = 0x07E0;
static constexpr uint16_t LCD_BLUE = 0x001F;

static constexpr int ONE_LINE_SPACE = 20;
static constexpr int TWO_LINES_SPACE = 40;
static constexpr int THREE_LINES_SPACE = 60;

// -----------------------------------------------------------------------------
// Minimal UI layout helpers ("OS template" building blocks)
// -----------------------------------------------------------------------------
struct UiRect {
    int16_t x;
    int16_t y;
    int16_t w;
    int16_t h;
};

// Default layout for 240x240 screens (works for other sizes too)
static constexpr int16_t UI_PADDING = 10;
static constexpr int16_t UI_STATUS_BAR_HEIGHT = 64;
static constexpr int16_t UI_FOOTER_HEIGHT = 70;
static constexpr int16_t UI_GAP = 6;

class DisplayManager {
   public:
    static void begin();
    static bool isReady();
    static void ensureInit();
    static Arduino_GFX* getGfx();
    static int16_t screenWidth();
    static int16_t screenHeight();
    static void drawStartup(String currentIP);
    static void drawTextWrapped(int16_t xPos, int16_t yPos, const String& text, uint8_t textSize, uint16_t fgColor,
                                uint16_t bgColor, bool clearBg);
    static void drawLoadingBar(float progress, int yPos = 180, int barWidth = 200, int barHeight = 20,
                               uint16_t fgColor = 0x07E0, uint16_t bgColor = 0x39E7);
    static bool playGifFullScreen(const String& path, uint32_t timeMs = 0);
    static bool stopGif();
    static void update();
    static void clearScreen();

    // Layout rectangles for a simple 3-region UI: status bar, body, footer (mascot)
    static UiRect getStatusBarRect();
    static UiRect getBodyRect();
    static UiRect getFooterRect();

    // Lightweight helpers for status/body rendering (intended for partial updates)
    static void drawStatusBar(const String& leftText, const String& rightText, bool wifiConnected, int8_t wifiBars,
                              int8_t batteryPct, bool charging, uint16_t fgColor = LCD_WHITE, uint16_t bgColor = LCD_BLACK,
                              bool clearBg = true);
    static void drawTrackerBar(int16_t waterCount, int16_t tomatoCount, int16_t pushupCount, bool supplementsDone,
                               uint16_t fgColor = LCD_WHITE, uint16_t bgColor = LCD_BLACK, bool clearBg = true);
    static void drawBodyText(const String& text, uint8_t textSize = 2, uint16_t fgColor = LCD_WHITE,
                             uint16_t bgColor = LCD_BLACK, bool clearBg = true);

    // Drawing primitives for custom screens
    static void fillScreen(uint16_t color);
    static void drawPixel(int16_t x, int16_t y, uint16_t color);
    static void drawLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color);
    static void drawRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color);
    static void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color);
    static void drawCircle(int16_t x, int16_t y, int16_t r, uint16_t color);
    static void fillCircle(int16_t x, int16_t y, int16_t r, uint16_t color);

    // Triangle primitives
    static void drawTriangle(int16_t x0, int16_t y0, int16_t x1, int16_t y1, int16_t x2, int16_t y2, uint16_t color);
    static void fillTriangle(int16_t x0, int16_t y0, int16_t x1, int16_t y1, int16_t x2, int16_t y2, uint16_t color);

    // Ellipse primitives
    static void drawEllipse(int16_t x, int16_t y, int16_t rx, int16_t ry, uint16_t color);
    static void fillEllipse(int16_t x, int16_t y, int16_t rx, int16_t ry, uint16_t color);

    // Rounded rectangle primitives
    static void drawRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint16_t color);
    static void fillRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint16_t color);

    // Helper to convert hex color string to RGB565
    static uint16_t hexToRgb565(const String& hex);
};
