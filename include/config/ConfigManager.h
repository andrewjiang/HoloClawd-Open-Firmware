#ifndef CONFIG_MANAGER_H
#define CONFIG_MANAGER_H

#include <ArduinoJson.h>
#include <string>
#include <cstdint>

class ConfigManager {
   public:
    ConfigManager(const char* filename = "/config.json");
    bool load();
    const char* getSSID() const;
    const char* getPassword() const;
    bool getLCDEnable() const;
    int16_t getLCDWidth() const;
    int16_t getLCDHeight() const;
    uint8_t getLCDRotation() const;
    int8_t getLCDMosiGpio() const;
    int8_t getLCDSckGpio() const;
    int8_t getLCDCsGpio() const;
    int8_t getLCDDcGpio() const;
    int8_t getLCDRstGpio() const;
    bool getLCDCsActiveHigh() const;
    bool getLCDDcCmdHigh() const;
    uint8_t getLCDSpiMode() const;
    bool getLCDKeepCsAsserted() const;
    uint32_t getLCDSpiHz() const;
    int8_t getLCDBacklightGpio() const;
    bool getLCDBacklightActiveLow() const;

   private:
    std::string ssid;
    std::string password;
    std::string filename;
    bool lcd_enable = true;
    int16_t lcd_w = 240;
    int16_t lcd_h = 240;
    uint8_t lcd_rotation = 4;
    int8_t lcd_mosi_gpio = 13;
    int8_t lcd_sck_gpio = 14;
    int8_t lcd_cs_gpio = 2;
    int8_t lcd_dc_gpio = 0;
    int8_t lcd_rst_gpio = 15;
    bool lcd_cs_active_high = true;
    bool lcd_dc_cmd_high = false;
    uint8_t lcd_spi_mode = 0;
    bool lcd_keep_cs_asserted = true;
    uint32_t lcd_spi_hz = 80000000;
    int8_t lcd_backlight_gpio = 5;
    bool lcd_backlight_active_low = true;
};

#endif  // CONFIG_MANAGER_H
