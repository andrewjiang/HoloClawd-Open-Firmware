#include <Arduino.h>
#include <LittleFS.h>
#include <Arduino_GFX_Library.h>
#include <SPI.h>

#include <Logger.h>
#include "project_version.h"
#include "config/ConfigManager.h"
#include "wireless/WiFiManager.h"
#include "display/DisplayManager.h"

ConfigManager configManager;
const char* AP_SSID = "HelloCubicLite";
const char* AP_PASSWORD = "$str0ngPa$$w0rd";
WiFiManager* wifiManager = nullptr;

static constexpr uint32_t SERIAL_BAUD_RATE = 115200;
static constexpr uint32_t BOOT_DELAY_MS = 200;

/**
 * @brief Initializes the system
 *
 */
void setup() {
    Serial.begin(SERIAL_BAUD_RATE);
    delay(BOOT_DELAY_MS);
    Serial.println("");
    Logger::info(("HelloCubic Lite Open Firmware " + String(PROJECT_VER_STR)).c_str());

    if (!LittleFS.begin()) {
        Logger::error("Failed to mount LittleFS");
        return;
    }

    if (configManager.load()) {
        Logger::info("Configuration loaded successfully");
    }

    wifiManager = new WiFiManager(configManager.getSSID(), configManager.getPassword(), AP_SSID, AP_PASSWORD);
    wifiManager->begin();

    DisplayManager::begin();
    if (DisplayManager::isReady()) {
        DisplayManager::drawStartup();
    }
}

void loop() {
    // put your main code here, to run repeatedly:
}
