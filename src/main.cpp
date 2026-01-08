#include <Arduino.h>
#include <LittleFS.h>

#include <Logger.h>
#include "config/ConfigManager.h"
#include "wireless/WiFiManager.h"

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
    Logger::info("HelloCubic Lite Open Firmware");

    if (!LittleFS.begin()) {
        Logger::error("Failed to mount LittleFS");
        return;
    }

    if (configManager.load()) {
        Logger::info("Configuration loaded successfully");
    }

    wifiManager = new WiFiManager(configManager.getSSID(), configManager.getPassword(), AP_SSID, AP_PASSWORD);
    wifiManager->begin();
}

void loop() {
    // put your main code here, to run repeatedly:
}
