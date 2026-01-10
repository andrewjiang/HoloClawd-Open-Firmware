#pragma once

#include <Arduino.h>
#include <Arduino_GFX_Library.h>

class DisplayManager {
   public:
    static void begin();
    static bool isReady();
    static void drawStartup();
    static void drawTextWrapped(int16_t xPos, int16_t yPos, const String& text, uint8_t textSize, uint16_t fgColor,
                                uint16_t bgColor, bool clearBg);
};
