#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <ESP8266WiFi.h>
#include <Arduino.h>
#include <ArduinoJson.h>

class WiFiManager {
   public:
    WiFiManager(const char* staSsid, const char* staPass, const char* apSsid, const char* apPass);
    void begin();
    bool startStationMode();
    bool startAccessPointMode();
    bool isApMode() const;
    IPAddress getIP() const;
    static void scanNetworks(JsonArray& out);
    bool connectToNetwork(const char* ssid, const char* pass, uint32_t timeoutMs = 10000);
    static bool isConnected();
    static String getConnectedSSID();

   private:
    const char* _staSsid;
    const char* _staPass;
    const char* _apSsid;
    const char* _apPass;
    bool _apMode = false;
};

#endif  // WIFI_MANAGER_H
