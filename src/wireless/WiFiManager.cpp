#include <Logger.h>
#include "wireless/WiFiManager.h"

/**
 * @brief Maximum number of attempts to connect to a wifi network
 */
static constexpr int MAX_CONNECTION_ATTEMPTS = 20;

/**
 * @brief Delay in milliseconds between wifi connection attempts
 */
static constexpr uint32_t CONNECTION_DELAY_MS = 500;

/**
 * @brief WifiManager constructor
 *
 * @param staSsid The SSID for the WiFi station mode
 * @param staPass The password for the WiFi station mode
 * @param apSsid The SSID for the WiFi access point mode
 * @param apPass The password for the WiFi access point mode
 */
WiFiManager::WiFiManager(const char* staSsid, const char* staPass, const char* apSsid, const char* apPass)
    : _staSsid(staSsid), _staPass(staPass), _apSsid(apSsid), _apPass(apPass) {}

auto WiFiManager::begin() -> void {
    if (!WiFiManager::startStationMode()) {
        WiFiManager::startAccessPointMode();
    }

    Logger::info("Wifi active", "WiFiManager");
    Logger::info(String("Mode : " + String(_apMode ? "AP" : "STA")).c_str(), "WiFiManager");
    Logger::info(String("SSID : " + String(_apMode ? _apSsid : _staSsid)).c_str(), "WiFiManager");
    Logger::info(String("IP   : " + WiFiManager::getIP().toString()).c_str(), "WiFiManager");
}

/**
 * @brief Attempts to connect the device to a WiFi network in station mode
 *
 * @return true if the device successfully connects to the WiFi network false otherwise
 */
auto WiFiManager::startStationMode() -> bool {
    WiFi.mode(WIFI_STA);
    WiFi.begin(_staSsid, _staPass);
    int attempts = 0;

    Logger::info("Connecting to WiFi...", "WiFiManager");

    while (WiFi.status() != WL_CONNECTED && attempts < MAX_CONNECTION_ATTEMPTS) {
        delay(CONNECTION_DELAY_MS);
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        _apMode = false;
        return true;
    }

    return false;
}

/**
 * @brief Starts the WiFi Access Point (AP) mode
 *
 * @return true Always returns true to indicate the AP mode was started
 */
auto WiFiManager::startAccessPointMode() -> bool {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(_apSsid, _apPass);

    _apMode = true;

    return true;
}

auto WiFiManager::isApMode() const -> bool { return _apMode; }

auto WiFiManager::getIP() const -> IPAddress { return _apMode ? WiFi.softAPIP() : WiFi.localIP(); }
