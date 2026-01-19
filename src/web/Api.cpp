#include <Arduino.h>
#include <Logger.h>
#include <ArduinoJson.h>
#include <ESP8266HTTPUpdateServer.h>
#include <Updater.h>

#include "web/Webserver.h"
#include "web/Api.h"
#include "display/DisplayManager.h"

#include "config/ConfigManager.h"
#include "wireless/WiFiManager.h"

extern ConfigManager configManager;
extern WiFiManager* wifiManager;

ESP8266HTTPUpdateServer httpUpdater;
static bool otaError = false;
static size_t otaSize = 0;
static String otaStatus;

static constexpr size_t JSON_DOC_WIFI_SCAN_SIZE = 4096;
static constexpr size_t JSON_DOC_SMALL_SIZE = 1024;
static constexpr int WIFI_CONNECT_TIMEOUT_MS = 15000;

/**
 * @brief Register API endpoints for the webserver
 * @param webserver Pointer to the Webserver instance
 *
 * @return void
 */
void registerApiEndpoints(Webserver* webserver) {
    Logger::info("Registering API endpoints", "API");

    webserver->raw().on("/api/v1/wifi/scan", HTTP_GET, [webserver]() { handleWifiScan(webserver); });
    webserver->raw().on("/api/v1/wifi/connect", HTTP_POST, [webserver]() { handleWifiConnect(webserver); });
    webserver->raw().on("/api/v1/wifi/status", HTTP_GET, [webserver]() { handleWifiStatus(webserver); });

    webserver->raw().on("/api/v1/reboot", HTTP_POST, [webserver]() { handleReboot(webserver); });

    // Just in case for now the old updater endpoint is still here
    httpUpdater.setup(&webserver->raw(), "/legacyupdate");

    webserver->raw().on(
        "/api/v1/ota/fw", HTTP_POST, [webserver]() { handleOtaFinished(webserver); },
        [webserver]() { handleOtaUpload(webserver, U_FLASH); });
    webserver->raw().on(
        "/api/v1/ota/fs", HTTP_POST, [webserver]() { handleOtaFinished(webserver); },
        [webserver]() { handleOtaUpload(webserver, U_FS); });

    webserver->raw().on(
        "/api/v1/gif", HTTP_POST, [webserver]() { handleGifUpload(webserver); },
        [webserver]() { handleGifUpload(webserver); });

    webserver->raw().on("/api/v1/gif/play", HTTP_POST, [webserver]() { handlePlayGif(webserver); });
    webserver->raw().on("/api/v1/gif/stop", HTTP_POST, [webserver]() { handleStopGif(webserver); });

    webserver->raw().on("/api/v1/gif", HTTP_GET, [webserver]() { handleListGifs(webserver); });

    // Drawing API endpoints
    webserver->raw().on("/api/v1/draw/clear", HTTP_POST, [webserver]() { handleDrawClear(webserver); });
    webserver->raw().on("/api/v1/draw/text", HTTP_POST, [webserver]() { handleDrawText(webserver); });
    webserver->raw().on("/api/v1/draw/rect", HTTP_POST, [webserver]() { handleDrawRect(webserver); });
    webserver->raw().on("/api/v1/draw/circle", HTTP_POST, [webserver]() { handleDrawCircle(webserver); });
    webserver->raw().on("/api/v1/draw/line", HTTP_POST, [webserver]() { handleDrawLine(webserver); });
    webserver->raw().on("/api/v1/draw/pixel", HTTP_POST, [webserver]() { handleDrawPixel(webserver); });
    webserver->raw().on("/api/v1/draw/triangle", HTTP_POST, [webserver]() { handleDrawTriangle(webserver); });
    webserver->raw().on("/api/v1/draw/ellipse", HTTP_POST, [webserver]() { handleDrawEllipse(webserver); });
    webserver->raw().on("/api/v1/draw/roundrect", HTTP_POST, [webserver]() { handleDrawRoundRect(webserver); });
    webserver->raw().on("/api/v1/draw/batch", HTTP_POST, [webserver]() { handleDrawBatch(webserver); });
}

/**
 * @brief List GIF files and FS info
 * @param webserver Pointer to the Webserver instance
 *
 * @return void
 */
void handleListGifs(Webserver* webserver) {
    JsonDocument doc;
    JsonArray files = doc["files"].to<JsonArray>();

    size_t usedBytes = 0;
    size_t totalBytes = 0;

    if (LittleFS.begin()) {
        Dir dir = LittleFS.openDir("/gif");

        while (dir.next()) {
            String name = dir.fileName();
            if (name.endsWith(".gif") || name.endsWith(".GIF")) {
                JsonObject fileObj = files.add<JsonObject>();

                fileObj["name"] = name;            // NOLINT(readability-misplaced-array-index)
                fileObj["size"] = dir.fileSize();  // NOLINT(readability-misplaced-array-index)
                usedBytes += dir.fileSize();
            }
        }

        FSInfo fs_info;

        if (LittleFS.info(fs_info)) {
            totalBytes = fs_info.totalBytes;
            usedBytes = fs_info.usedBytes;
        }
    }

    doc["usedBytes"] = usedBytes;
    doc["totalBytes"] = totalBytes;
    doc["freeBytes"] = totalBytes > usedBytes ? totalBytes - usedBytes : 0;

    String json;
    serializeJson(doc, json);
    webserver->raw().send(HTTP_CODE_OK, "application/json", json);
}

/**
 * @brief Handle GIF upload start
 * @param currentFilename The current filename being uploaded
 * @param gifFile Reference to the File object for the GIF
 * @param uploadError Reference to the upload error flag
 *
 * @return void
 */
void handleGifUploadStart(const String& currentFilename, File& gifFile, bool& uploadError) {
    uploadError = false;
    Logger::info((String("UPLOAD_FILE_START for: ") + currentFilename).c_str(), "API::GIF");
    if (!LittleFS.exists("/gif")) {
        Logger::info("/gif directory does not exist, creating...", "API::GIF");
        if (!LittleFS.mkdir("/gif")) {
            Logger::error("Failed to create /gif directory!", "API::GIF");
        }
    }
    gifFile = LittleFS.open(currentFilename, "w");
    if (!gifFile) {
        uploadError = true;
        Logger::error((String("Impossible to open file: ") + currentFilename).c_str(), "API::GIF");
        Logger::error("GIF UPLOAD Failed to open file", "API::GIF");
    } else {
        Logger::info("File opened successfully for writing.", "API::GIF");
    }
}

/**
 * @brief Handle GIF upload write
 * @param upload Reference to the HTTPUpload object
 * @param gifFile Reference to the File object for the GIF
 * @param uploadError Reference to the upload error flag
 *
 * @return void
 */
void handleGifUploadWrite(HTTPUpload& upload, File& gifFile, bool& uploadError) {
    if (!uploadError && gifFile) {
        size_t total = 0;
        while (total < upload.currentSize) {
            size_t remaining = upload.currentSize - total;
            int toWrite = static_cast<int>(remaining > static_cast<size_t>(INT_MAX) ? INT_MAX : remaining);
            size_t written = gifFile.write(upload.buf + total, toWrite);

            if (written == 0) {
                Logger::error("Write returned 0 bytes!", "API::GIF");
                uploadError = true;
                break;
            }
            total += written;
        }
    } else {
        Logger::error("Cannot write, file not open or previous error", "API::GIF");
    }
}

/**
 * @brief Handle GIF upload end
 * @param currentFilename The current filename being uploaded
 * @param gifFile Reference to the File object for the GIF
 *
 * @return void
 */
void handleGifUploadEnd(const String& currentFilename, File& gifFile) {
    if (gifFile) {
        gifFile.close();
    }

    Logger::info((String("Gif upload end: ") + currentFilename).c_str(), "API::GIF");
}

/**
 * @brief Handle GIF upload aborted
 * @param currentFilename The current filename being uploaded
 * @param gifFile Reference to the File object for the GIF
 * @param uploadError Reference to the upload error flag
 *
 * @return void
 */
void handleGifUploadAborted(const String& currentFilename, File& gifFile, bool& uploadError) {
    Logger::warn("UPLOAD_FILE_ABORTED", "API::GIF");
    if (gifFile) {
        gifFile.close();
        Logger::warn("File closed after abort", "API::GIF");
    }
    if (!currentFilename.isEmpty()) {
        if (LittleFS.remove(currentFilename)) {
            Logger::warn((String("Removed incomplete file: ") + currentFilename).c_str(), "API::GIF");
        } else {
            Logger::error((String("Failed to remove incomplete file: ") + currentFilename).c_str(), "API::GIF");
        }
    }
    uploadError = true;
}

/**
 * @brief Send GIF upload result
 * @param webserver Pointer to the Webserver instance
 * @param currentFilename The current filename being uploaded
 * @param uploadError The upload error flag
 *
 * @return void
 */
void sendGifUploadResult(Webserver* webserver, const String& currentFilename, bool uploadError) {
    JsonDocument doc;
    if (uploadError) {
        doc["status"] = "error";
        doc["message"] = "Error during GIF upload";
        Logger::error("GIF UPLOAD Error during upload", "API::GIF");
    } else {
        doc["status"] = "success";
        doc["message"] = "GIF uploaded successfully";
        doc["filename"] = currentFilename;
        Logger::info((String("Gif upload success, filename: ") + currentFilename).c_str(), "API::GIF");
    }
    String json;
    serializeJson(doc, json);
    webserver->raw().send(HTTP_CODE_OK, "application/json", json);
}

/**
 * @brief Handle GIF upload
 * @param webserver Pointer to the Webserver instance
 *
 * @return void
 */
void handleGifUpload(Webserver* webserver) {
    HTTPUpload& upload = webserver->raw().upload();
    static File gifFile;
    static bool uploadError = false;

    String filename = upload.filename;
    filename.replace("\\", "/");
    filename = filename.substring(filename.lastIndexOf('/') + 1);
    String currentFilename = "/gif/" + filename;

    switch (upload.status) {
        case UPLOAD_FILE_START:
            handleGifUploadStart(currentFilename, gifFile, uploadError);
            break;
        case UPLOAD_FILE_WRITE:
            handleGifUploadWrite(upload, gifFile, uploadError);
            break;
        case UPLOAD_FILE_END:
            handleGifUploadEnd(currentFilename, gifFile);
            break;
        case UPLOAD_FILE_ABORTED:
            handleGifUploadAborted(currentFilename, gifFile, uploadError);
            break;
        default:
            Logger::warn("Unknown upload status.", "API::GIF");
            break;
    }

    if (upload.status == UPLOAD_FILE_END || upload.status == UPLOAD_FILE_ABORTED) {
        sendGifUploadResult(webserver, currentFilename, uploadError);
    }
}

/**
 * @brief Reboot endpoint
 * @param webserver Pointer to the Webserver instance
 *
 * @return void
 */
void handleReboot(Webserver* webserver) {
    JsonDocument doc;
    int constexpr rebootDelayMs = 1000;

    doc["status"] = "rebooting";
    String json;
    serializeJson(doc, json);

    webserver->raw().send(HTTP_CODE_OK, "application/json", json);

    delay(rebootDelayMs);
    ESP.restart();  // NOLINT(readability-static-accessed-through-instance)
}

/**
 * @brief Handle OTA upload
 * @param webserver Pointer to the Webserver instance
 * @param mode Update mode U_FLASH U_FS
 *
 * @return void
 */
void handleOtaUpload(Webserver* webserver, int mode) {
    HTTPUpload& upload = webserver->raw().upload();

    switch (upload.status) {
        case UPLOAD_FILE_START: {
            Logger::info(("OTA start: " + upload.filename).c_str(), "API::OTA");

            otaError = false;
            otaSize = 0;
            otaStatus = "";
            int constexpr security_space = 0x1000;
            u_int constexpr bin_mask = 0xFFFFF000;

            FSInfo fs_info;
            LittleFS.info(fs_info);
            size_t fsSize = fs_info.totalBytes;
            size_t maxSketchSpace =
                (ESP.getFreeSketchSpace() - security_space) &  // NOLINT(readability-static-accessed-through-instance)
                bin_mask;
            size_t place = (mode == U_FS) ? fsSize : maxSketchSpace;

            if (!Update.begin(place, mode)) {
                otaError = true;
                otaStatus = Update.getErrorString();
                Logger::error(("Update.begin failed: " + otaStatus).c_str(), "API::OTA");
            }

            break;
        }

        case UPLOAD_FILE_WRITE: {
            if (!otaError) {
                if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
                    otaError = true;
                    otaStatus = Update.getErrorString();
                    Logger::error(("Write failed: " + otaStatus).c_str(), "API::OTA");
                }
                otaSize += upload.currentSize;
            }

            break;
        }

        case UPLOAD_FILE_END: {
            if (!otaError) {
                if (Update.end(true)) {
                    if (mode == U_FS) {
                        Logger::info("OTA FS update complete, mounting file system...", "API::OTA");
                        LittleFS.begin();
                    }

                    otaStatus = "Update OK (" + String(otaSize) + " bytes)";
                    Logger::info(otaStatus.c_str(), "API::OTA");
                } else {
                    otaError = true;
                    otaStatus = Update.getErrorString();
                }
            }

            break;
        }

        case UPLOAD_FILE_ABORTED: {
            Update.end();
            otaError = true;
            otaStatus = "Update aborted";

            break;
        }

        default:
            break;
    }
}

/**
 * @brief Handle OTA finished
 * @param webserver Pointer to the Webserver instance
 *
 * @return void
 */
void handleOtaFinished(Webserver* webserver) {
    JsonDocument doc;
    int constexpr rebootDelayMs = 5000;

    doc["status"] = "Upload successful";
    doc["message"] = otaStatus;

    if (otaError) {
        doc["status"] = "Error";
    }

    String json;
    serializeJson(doc, json);
    webserver->raw().send(HTTP_CODE_OK, "application/json", json);

    if (!otaError) {
        delay(rebootDelayMs);
        ESP.restart();  // NOLINT(readability-static-accessed-through-instance)
    }
}

/**
 * @brief Play a GIF from LittleFS full screen
 *
 * @param webserver Pointer to the Webserver instance
 *
 * @return void
 */
void handlePlayGif(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;

        resp["status"] = "error";
        resp["message"] = "invalid json";

        String jsonOut;

        serializeJson(resp, jsonOut);

        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);

        return;
    }

    const char* name = doc["name"];
    if (name == nullptr || strlen(name) == 0) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "missing name";

        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);

        return;
    }

    String filename(name);
    filename.replace("\\", "/");
    filename = filename.substring(filename.lastIndexOf('/') + 1);

    String path1 = String("/gifs/") + filename;
    String path2 = String("/gif/") + filename;
    String foundPath;

    if (LittleFS.exists(path1)) {
        foundPath = path1;
    } else if (LittleFS.exists(path2)) {
        foundPath = path2;
    } else {
        JsonDocument resp;

        resp["status"] = "error";
        resp["message"] = "file not found";

        String jsonOut;
        serializeJson(resp, jsonOut);

        webserver->raw().send(HTTP_CODE_NOT_FOUND, "application/json", jsonOut);

        return;
    }

    bool playOk = DisplayManager::playGifFullScreen(foundPath);

    JsonDocument resp;

    resp["status"] = playOk ? "playing" : "error";
    resp["file"] = foundPath;

    String jsonOut;

    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Stop currently playing GIF
 */
void handleStopGif(Webserver* webserver) {
    JsonDocument resp;

    const bool stopped = DisplayManager::stopGif();

    resp["status"] = stopped ? "stopped" : "error";

    String jsonOut;
    serializeJson(resp, jsonOut);

    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Handle WiFi scan
 */
void handleWifiScan(Webserver* webserver) {
    JsonDocument doc;
    JsonArray networks = doc["networks"].to<JsonArray>();

    if (wifiManager != nullptr) {
        WiFiManager::scanNetworks(networks);
    }

    String out;
    serializeJson(doc["networks"], out);
    webserver->raw().send(HTTP_CODE_OK, "application/json", out);
}

/**
 * @brief Handle WiFi connect request
 */
void handleWifiConnect(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;

        resp["status"] = "error";
        resp["message"] = "invalid json";

        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);

        return;
    }

    const char* ssid = doc["ssid"] | "";
    const char* password = doc["password"] | "";

    if (strlen(ssid) == 0) {
        JsonDocument resp;

        resp["status"] = "error";
        resp["message"] = "missing ssid";

        String jsonOut;

        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);

        return;
    }

    bool connectOk = false;
    if (wifiManager != nullptr) {
        connectOk = wifiManager->connectToNetwork(ssid, password, WIFI_CONNECT_TIMEOUT_MS);
    }

    JsonDocument resp;

    resp["status"] = connectOk ? "connected" : "error";
    resp["ssid"] = ssid;

    if (connectOk) {
        resp["ip"] = wifiManager->getIP().toString();
        configManager.setWiFi(ssid, password);
        configManager.save();
    }

    if (!connectOk) {
        resp["message"] = "failed to connect";
    }

    String jsonOut;
    serializeJson(resp, jsonOut);

    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief WiFi status
 */
void handleWifiStatus(Webserver* webserver) {
    JsonDocument resp;

    bool connected = (wifiManager != nullptr) && WiFiManager::isConnected();

    resp["connected"] = connected;
    resp["ssid"] = connected ? WiFiManager::getConnectedSSID() : "";
    resp["ip"] = connected ? wifiManager->getIP().toString() : "";

    String jsonOut;
    serializeJson(resp, jsonOut);

    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

// ============================================================================
// Drawing API Handlers
// ============================================================================

/**
 * @brief Clear the screen
 * POST /api/v1/draw/clear
 * Body: {"color": "#000000"} (optional, defaults to black)
 */
void handleDrawClear(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    uint16_t color = LCD_BLACK;

    if (body.length() > 0) {
        DeserializationError err = deserializeJson(doc, body);
        if (!err && doc.containsKey("color")) {
            color = DisplayManager::hexToRgb565(doc["color"].as<String>());
        }
    }

    DisplayManager::fillScreen(color);

    JsonDocument resp;
    resp["status"] = "ok";

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Draw text on screen
 * POST /api/v1/draw/text
 * Body: {"x": 10, "y": 10, "text": "Hello", "size": 2, "color": "#ffffff", "bg": "#000000"}
 */
void handleDrawText(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "invalid json";
        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
        return;
    }

    int16_t x = doc["x"] | 0;
    int16_t y = doc["y"] | 0;
    String text = doc["text"] | "";
    uint8_t size = doc["size"] | 2;
    uint16_t fgColor = LCD_WHITE;
    uint16_t bgColor = LCD_BLACK;

    if (doc.containsKey("color")) {
        fgColor = DisplayManager::hexToRgb565(doc["color"].as<String>());
    }
    if (doc.containsKey("bg")) {
        bgColor = DisplayManager::hexToRgb565(doc["bg"].as<String>());
    }

    bool clearBg = doc["clear"] | false;
    DisplayManager::drawTextWrapped(x, y, text, size, fgColor, bgColor, clearBg);

    JsonDocument resp;
    resp["status"] = "ok";

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Draw rectangle
 * POST /api/v1/draw/rect
 * Body: {"x": 10, "y": 10, "w": 50, "h": 50, "color": "#ff0000", "fill": true}
 */
void handleDrawRect(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "invalid json";
        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
        return;
    }

    int16_t x = doc["x"] | 0;
    int16_t y = doc["y"] | 0;
    int16_t w = doc["w"] | 10;
    int16_t h = doc["h"] | 10;
    bool fill = doc["fill"] | true;
    uint16_t color = LCD_WHITE;

    if (doc.containsKey("color")) {
        color = DisplayManager::hexToRgb565(doc["color"].as<String>());
    }

    if (fill) {
        DisplayManager::fillRect(x, y, w, h, color);
    } else {
        DisplayManager::drawRect(x, y, w, h, color);
    }

    JsonDocument resp;
    resp["status"] = "ok";

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Draw circle
 * POST /api/v1/draw/circle
 * Body: {"x": 120, "y": 120, "r": 50, "color": "#00ff00", "fill": true}
 */
void handleDrawCircle(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "invalid json";
        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
        return;
    }

    int16_t x = doc["x"] | 120;
    int16_t y = doc["y"] | 120;
    int16_t r = doc["r"] | 50;
    bool fill = doc["fill"] | true;
    uint16_t color = LCD_WHITE;

    if (doc.containsKey("color")) {
        color = DisplayManager::hexToRgb565(doc["color"].as<String>());
    }

    if (fill) {
        DisplayManager::fillCircle(x, y, r, color);
    } else {
        DisplayManager::drawCircle(x, y, r, color);
    }

    JsonDocument resp;
    resp["status"] = "ok";

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Draw line
 * POST /api/v1/draw/line
 * Body: {"x0": 0, "y0": 0, "x1": 240, "y1": 240, "color": "#0000ff"}
 */
void handleDrawLine(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "invalid json";
        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
        return;
    }

    int16_t x0 = doc["x0"] | 0;
    int16_t y0 = doc["y0"] | 0;
    int16_t x1 = doc["x1"] | 240;
    int16_t y1 = doc["y1"] | 240;
    uint16_t color = LCD_WHITE;

    if (doc.containsKey("color")) {
        color = DisplayManager::hexToRgb565(doc["color"].as<String>());
    }

    DisplayManager::drawLine(x0, y0, x1, y1, color);

    JsonDocument resp;
    resp["status"] = "ok";

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Draw pixel
 * POST /api/v1/draw/pixel
 * Body: {"x": 120, "y": 120, "color": "#ffffff"}
 */
void handleDrawPixel(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "invalid json";
        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
        return;
    }

    int16_t x = doc["x"] | 0;
    int16_t y = doc["y"] | 0;
    uint16_t color = LCD_WHITE;

    if (doc.containsKey("color")) {
        color = DisplayManager::hexToRgb565(doc["color"].as<String>());
    }

    DisplayManager::drawPixel(x, y, color);

    JsonDocument resp;
    resp["status"] = "ok";

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Draw triangle
 * POST /api/v1/draw/triangle
 * Body: {"x0": 100, "y0": 50, "x1": 50, "y1": 150, "x2": 150, "y2": 150, "color": "#ff0000", "fill": true}
 */
void handleDrawTriangle(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "invalid json";
        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
        return;
    }

    int16_t x0 = doc["x0"] | 0;
    int16_t y0 = doc["y0"] | 0;
    int16_t x1 = doc["x1"] | 0;
    int16_t y1 = doc["y1"] | 0;
    int16_t x2 = doc["x2"] | 0;
    int16_t y2 = doc["y2"] | 0;
    bool fill = doc["fill"] | true;
    uint16_t color = LCD_WHITE;

    if (doc.containsKey("color")) {
        color = DisplayManager::hexToRgb565(doc["color"].as<String>());
    }

    if (fill) {
        DisplayManager::fillTriangle(x0, y0, x1, y1, x2, y2, color);
    } else {
        DisplayManager::drawTriangle(x0, y0, x1, y1, x2, y2, color);
    }

    JsonDocument resp;
    resp["status"] = "ok";

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Draw ellipse
 * POST /api/v1/draw/ellipse
 * Body: {"x": 120, "y": 120, "rx": 50, "ry": 30, "color": "#00ff00", "fill": true}
 */
void handleDrawEllipse(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "invalid json";
        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
        return;
    }

    int16_t x = doc["x"] | 120;
    int16_t y = doc["y"] | 120;
    int16_t rx = doc["rx"] | 50;
    int16_t ry = doc["ry"] | 30;
    bool fill = doc["fill"] | true;
    uint16_t color = LCD_WHITE;

    if (doc.containsKey("color")) {
        color = DisplayManager::hexToRgb565(doc["color"].as<String>());
    }

    if (fill) {
        DisplayManager::fillEllipse(x, y, rx, ry, color);
    } else {
        DisplayManager::drawEllipse(x, y, rx, ry, color);
    }

    JsonDocument resp;
    resp["status"] = "ok";

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Draw rounded rectangle
 * POST /api/v1/draw/roundrect
 * Body: {"x": 10, "y": 10, "w": 100, "h": 50, "r": 10, "color": "#0000ff", "fill": true}
 */
void handleDrawRoundRect(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "invalid json";
        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
        return;
    }

    int16_t x = doc["x"] | 0;
    int16_t y = doc["y"] | 0;
    int16_t w = doc["w"] | 50;
    int16_t h = doc["h"] | 30;
    int16_t r = doc["r"] | 5;
    bool fill = doc["fill"] | true;
    uint16_t color = LCD_WHITE;

    if (doc.containsKey("color")) {
        color = DisplayManager::hexToRgb565(doc["color"].as<String>());
    }

    if (fill) {
        DisplayManager::fillRoundRect(x, y, w, h, r, color);
    } else {
        DisplayManager::drawRoundRect(x, y, w, h, r, color);
    }

    JsonDocument resp;
    resp["status"] = "ok";

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

/**
 * @brief Draw multiple primitives in one request (batch)
 * POST /api/v1/draw/batch
 * Body: {"commands": [
 *   {"type": "clear", "color": "#000000"},
 *   {"type": "rect", "x": 10, "y": 10, "w": 50, "h": 50, "color": "#ff0000", "fill": true},
 *   {"type": "text", "x": 70, "y": 100, "text": "Hello", "size": 2, "color": "#ffffff"},
 *   {"type": "circle", "x": 180, "y": 60, "r": 30, "color": "#00ff00", "fill": true},
 *   {"type": "line", "x0": 0, "y0": 0, "x1": 240, "y1": 240, "color": "#0000ff"}
 * ]}
 */
void handleDrawBatch(Webserver* webserver) {
    String body = webserver->raw().arg("plain");
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);

    if (err) {
        JsonDocument resp;
        resp["status"] = "error";
        resp["message"] = "invalid json";
        String jsonOut;
        serializeJson(resp, jsonOut);
        webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
        return;
    }

    JsonArray commands = doc["commands"].as<JsonArray>();
    int processed = 0;

    for (JsonObject cmd : commands) {
        String type = cmd["type"] | "";
        uint16_t color = LCD_WHITE;

        if (cmd.containsKey("color")) {
            color = DisplayManager::hexToRgb565(cmd["color"].as<String>());
        }

        if (type == "clear") {
            DisplayManager::fillScreen(color);
        } else if (type == "rect") {
            int16_t x = cmd["x"] | 0;
            int16_t y = cmd["y"] | 0;
            int16_t w = cmd["w"] | 10;
            int16_t h = cmd["h"] | 10;
            bool fill = cmd["fill"] | true;

            if (fill) {
                DisplayManager::fillRect(x, y, w, h, color);
            } else {
                DisplayManager::drawRect(x, y, w, h, color);
            }
        } else if (type == "circle") {
            int16_t x = cmd["x"] | 120;
            int16_t y = cmd["y"] | 120;
            int16_t r = cmd["r"] | 50;
            bool fill = cmd["fill"] | true;

            if (fill) {
                DisplayManager::fillCircle(x, y, r, color);
            } else {
                DisplayManager::drawCircle(x, y, r, color);
            }
        } else if (type == "line") {
            int16_t x0 = cmd["x0"] | 0;
            int16_t y0 = cmd["y0"] | 0;
            int16_t x1 = cmd["x1"] | 240;
            int16_t y1 = cmd["y1"] | 240;
            DisplayManager::drawLine(x0, y0, x1, y1, color);
        } else if (type == "pixel") {
            int16_t x = cmd["x"] | 0;
            int16_t y = cmd["y"] | 0;
            DisplayManager::drawPixel(x, y, color);
        } else if (type == "text") {
            int16_t x = cmd["x"] | 0;
            int16_t y = cmd["y"] | 0;
            String text = cmd["text"] | "";
            uint8_t size = cmd["size"] | 2;
            uint16_t bgColor = LCD_BLACK;
            if (cmd.containsKey("bg")) {
                bgColor = DisplayManager::hexToRgb565(cmd["bg"].as<String>());
            }
            bool clearBg = cmd["clear"] | false;
            DisplayManager::drawTextWrapped(x, y, text, size, color, bgColor, clearBg);
        } else if (type == "triangle") {
            int16_t x0 = cmd["x0"] | 0;
            int16_t y0 = cmd["y0"] | 0;
            int16_t x1 = cmd["x1"] | 0;
            int16_t y1 = cmd["y1"] | 0;
            int16_t x2 = cmd["x2"] | 0;
            int16_t y2 = cmd["y2"] | 0;
            bool fill = cmd["fill"] | true;
            if (fill) {
                DisplayManager::fillTriangle(x0, y0, x1, y1, x2, y2, color);
            } else {
                DisplayManager::drawTriangle(x0, y0, x1, y1, x2, y2, color);
            }
        } else if (type == "ellipse") {
            int16_t x = cmd["x"] | 120;
            int16_t y = cmd["y"] | 120;
            int16_t rx = cmd["rx"] | 50;
            int16_t ry = cmd["ry"] | 30;
            bool fill = cmd["fill"] | true;
            if (fill) {
                DisplayManager::fillEllipse(x, y, rx, ry, color);
            } else {
                DisplayManager::drawEllipse(x, y, rx, ry, color);
            }
        } else if (type == "roundrect") {
            int16_t x = cmd["x"] | 0;
            int16_t y = cmd["y"] | 0;
            int16_t w = cmd["w"] | 50;
            int16_t h = cmd["h"] | 30;
            int16_t r = cmd["r"] | 5;
            bool fill = cmd["fill"] | true;
            if (fill) {
                DisplayManager::fillRoundRect(x, y, w, h, r, color);
            } else {
                DisplayManager::drawRoundRect(x, y, w, h, r, color);
            }
        }

        processed++;
        yield();  // Allow other tasks to run between commands
    }

    JsonDocument resp;
    resp["status"] = "ok";
    resp["processed"] = processed;

    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}