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

// Default values for drawing primitives
static constexpr int16_t DEFAULT_POS = 0;
static constexpr int16_t DEFAULT_CENTER = 120;
static constexpr int16_t DEFAULT_SIZE_SMALL = 10;
static constexpr int16_t DEFAULT_SIZE_MEDIUM = 30;
static constexpr int16_t DEFAULT_SIZE_LARGE = 50;
static constexpr int16_t DEFAULT_CORNER_RADIUS = 5;
static constexpr int16_t SCREEN_SIZE = 240;
static constexpr uint8_t DEFAULT_TEXT_SIZE = 2;

// Helper to get color from JSON, returns LCD_WHITE if not present
static auto getColorFromJson(const JsonVariant& obj, const char* key = "color") -> uint16_t {
    if (obj.containsKey(key)) {
        return DisplayManager::hexToRgb565(obj[key].as<String>());
    }
    return LCD_WHITE;
}

// Helper to send success response
static auto sendSuccessResponse(Webserver* webserver) -> void {
    JsonDocument resp;
    resp["status"] = "ok";
    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_OK, "application/json", jsonOut);
}

// Helper to send error response
static auto sendErrorResponse(Webserver* webserver, const char* message) -> void {
    JsonDocument resp;
    resp["status"] = "error";
    resp["message"] = message;
    String jsonOut;
    serializeJson(resp, jsonOut);
    webserver->raw().send(HTTP_CODE_INTERNAL_ERROR, "application/json", jsonOut);
}

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
    sendSuccessResponse(webserver);
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
        sendErrorResponse(webserver, "invalid json");
        return;
    }

    int16_t posX = doc["x"] | DEFAULT_POS;
    int16_t posY = doc["y"] | DEFAULT_POS;
    String text = doc["text"] | "";
    uint8_t textSize = doc["size"] | DEFAULT_TEXT_SIZE;
    uint16_t fgColor = getColorFromJson(doc);
    uint16_t bgColor = LCD_BLACK;

    if (doc.containsKey("bg")) {
        bgColor = DisplayManager::hexToRgb565(doc["bg"].as<String>());
    }

    bool clearBg = doc["clear"] | false;
    DisplayManager::drawTextWrapped(posX, posY, text, textSize, fgColor, bgColor, clearBg);
    sendSuccessResponse(webserver);
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
        sendErrorResponse(webserver, "invalid json");
        return;
    }

    int16_t posX = doc["x"] | DEFAULT_POS;
    int16_t posY = doc["y"] | DEFAULT_POS;
    int16_t width = doc["w"] | DEFAULT_SIZE_SMALL;
    int16_t height = doc["h"] | DEFAULT_SIZE_SMALL;
    bool shouldFill = doc["fill"] | true;
    uint16_t color = getColorFromJson(doc);

    if (shouldFill) {
        DisplayManager::fillRect(posX, posY, width, height, color);
    } else {
        DisplayManager::drawRect(posX, posY, width, height, color);
    }
    sendSuccessResponse(webserver);
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
        sendErrorResponse(webserver, "invalid json");
        return;
    }

    int16_t posX = doc["x"] | DEFAULT_CENTER;
    int16_t posY = doc["y"] | DEFAULT_CENTER;
    int16_t radius = doc["r"] | DEFAULT_SIZE_LARGE;
    bool shouldFill = doc["fill"] | true;
    uint16_t color = getColorFromJson(doc);

    if (shouldFill) {
        DisplayManager::fillCircle(posX, posY, radius, color);
    } else {
        DisplayManager::drawCircle(posX, posY, radius, color);
    }
    sendSuccessResponse(webserver);
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
        sendErrorResponse(webserver, "invalid json");
        return;
    }

    int16_t startX = doc["x0"] | DEFAULT_POS;
    int16_t startY = doc["y0"] | DEFAULT_POS;
    int16_t endX = doc["x1"] | SCREEN_SIZE;
    int16_t endY = doc["y1"] | SCREEN_SIZE;
    uint16_t color = getColorFromJson(doc);

    DisplayManager::drawLine(startX, startY, endX, endY, color);
    sendSuccessResponse(webserver);
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
        sendErrorResponse(webserver, "invalid json");
        return;
    }

    int16_t posX = doc["x"] | DEFAULT_POS;
    int16_t posY = doc["y"] | DEFAULT_POS;
    uint16_t color = getColorFromJson(doc);

    DisplayManager::drawPixel(posX, posY, color);
    sendSuccessResponse(webserver);
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
        sendErrorResponse(webserver, "invalid json");
        return;
    }

    int16_t vertX0 = doc["x0"] | DEFAULT_POS;
    int16_t vertY0 = doc["y0"] | DEFAULT_POS;
    int16_t vertX1 = doc["x1"] | DEFAULT_POS;
    int16_t vertY1 = doc["y1"] | DEFAULT_POS;
    int16_t vertX2 = doc["x2"] | DEFAULT_POS;
    int16_t vertY2 = doc["y2"] | DEFAULT_POS;
    bool shouldFill = doc["fill"] | true;
    uint16_t color = getColorFromJson(doc);

    if (shouldFill) {
        DisplayManager::fillTriangle(vertX0, vertY0, vertX1, vertY1, vertX2, vertY2, color);
    } else {
        DisplayManager::drawTriangle(vertX0, vertY0, vertX1, vertY1, vertX2, vertY2, color);
    }
    sendSuccessResponse(webserver);
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
        sendErrorResponse(webserver, "invalid json");
        return;
    }

    int16_t posX = doc["x"] | DEFAULT_CENTER;
    int16_t posY = doc["y"] | DEFAULT_CENTER;
    int16_t radiusX = doc["rx"] | DEFAULT_SIZE_LARGE;
    int16_t radiusY = doc["ry"] | DEFAULT_SIZE_MEDIUM;
    bool shouldFill = doc["fill"] | true;
    uint16_t color = getColorFromJson(doc);

    if (shouldFill) {
        DisplayManager::fillEllipse(posX, posY, radiusX, radiusY, color);
    } else {
        DisplayManager::drawEllipse(posX, posY, radiusX, radiusY, color);
    }
    sendSuccessResponse(webserver);
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
        sendErrorResponse(webserver, "invalid json");
        return;
    }

    int16_t posX = doc["x"] | DEFAULT_POS;
    int16_t posY = doc["y"] | DEFAULT_POS;
    int16_t width = doc["w"] | DEFAULT_SIZE_LARGE;
    int16_t height = doc["h"] | DEFAULT_SIZE_MEDIUM;
    int16_t radius = doc["r"] | DEFAULT_CORNER_RADIUS;
    bool shouldFill = doc["fill"] | true;
    uint16_t color = getColorFromJson(doc);

    if (shouldFill) {
        DisplayManager::fillRoundRect(posX, posY, width, height, radius, color);
    } else {
        DisplayManager::drawRoundRect(posX, posY, width, height, radius, color);
    }
    sendSuccessResponse(webserver);
}

// Helper to safely get int16_t from JSON with default
static auto getInt16(const JsonObject& obj, const char* key, int16_t defaultVal) -> int16_t {
    return obj.containsKey(key) ? static_cast<int16_t>(obj[key].as<int>()) : defaultVal;
}

// Helper to safely get bool from JSON with default
static auto getBool(const JsonObject& obj, const char* key, bool defaultVal) -> bool {
    return obj.containsKey(key) ? (obj[key].as<int>() != 0) : defaultVal;
}

// Helper functions for batch processing to reduce cognitive complexity
static auto processBatchRect(const JsonObject& cmd, uint16_t color) -> void {
    int16_t posX = getInt16(cmd, "x", DEFAULT_POS);
    int16_t posY = getInt16(cmd, "y", DEFAULT_POS);
    int16_t width = getInt16(cmd, "w", DEFAULT_SIZE_SMALL);
    int16_t height = getInt16(cmd, "h", DEFAULT_SIZE_SMALL);
    bool shouldFill = getBool(cmd, "fill", true);
    if (shouldFill) {
        DisplayManager::fillRect(posX, posY, width, height, color);
    } else {
        DisplayManager::drawRect(posX, posY, width, height, color);
    }
}

static auto processBatchCircle(const JsonObject& cmd, uint16_t color) -> void {
    int16_t posX = getInt16(cmd, "x", DEFAULT_CENTER);
    int16_t posY = getInt16(cmd, "y", DEFAULT_CENTER);
    int16_t radius = getInt16(cmd, "r", DEFAULT_SIZE_LARGE);
    bool shouldFill = getBool(cmd, "fill", true);
    if (shouldFill) {
        DisplayManager::fillCircle(posX, posY, radius, color);
    } else {
        DisplayManager::drawCircle(posX, posY, radius, color);
    }
}

static auto processBatchLine(const JsonObject& cmd, uint16_t color) -> void {
    int16_t startX = getInt16(cmd, "x0", DEFAULT_POS);
    int16_t startY = getInt16(cmd, "y0", DEFAULT_POS);
    int16_t endX = getInt16(cmd, "x1", SCREEN_SIZE);
    int16_t endY = getInt16(cmd, "y1", SCREEN_SIZE);
    DisplayManager::drawLine(startX, startY, endX, endY, color);
}

static auto processBatchPixel(const JsonObject& cmd, uint16_t color) -> void {
    int16_t posX = getInt16(cmd, "x", DEFAULT_POS);
    int16_t posY = getInt16(cmd, "y", DEFAULT_POS);
    DisplayManager::drawPixel(posX, posY, color);
}

static auto processBatchText(const JsonObject& cmd, uint16_t color) -> void {
    int16_t posX = getInt16(cmd, "x", DEFAULT_POS);
    int16_t posY = getInt16(cmd, "y", DEFAULT_POS);
    String text = cmd.containsKey("text") ? cmd["text"].as<String>() : "";
    uint8_t textSize = cmd.containsKey("size") ? static_cast<uint8_t>(cmd["size"].as<int>()) : DEFAULT_TEXT_SIZE;
    uint16_t bgColor = LCD_BLACK;
    if (cmd.containsKey("bg")) {
        bgColor = DisplayManager::hexToRgb565(cmd["bg"].as<String>());
    }
    bool clearBg = getBool(cmd, "clear", false);
    DisplayManager::drawTextWrapped(posX, posY, text, textSize, color, bgColor, clearBg);
}

static auto processBatchTriangle(const JsonObject& cmd, uint16_t color) -> void {
    int16_t vertX0 = getInt16(cmd, "x0", DEFAULT_POS);
    int16_t vertY0 = getInt16(cmd, "y0", DEFAULT_POS);
    int16_t vertX1 = getInt16(cmd, "x1", DEFAULT_POS);
    int16_t vertY1 = getInt16(cmd, "y1", DEFAULT_POS);
    int16_t vertX2 = getInt16(cmd, "x2", DEFAULT_POS);
    int16_t vertY2 = getInt16(cmd, "y2", DEFAULT_POS);
    bool shouldFill = getBool(cmd, "fill", true);
    if (shouldFill) {
        DisplayManager::fillTriangle(vertX0, vertY0, vertX1, vertY1, vertX2, vertY2, color);
    } else {
        DisplayManager::drawTriangle(vertX0, vertY0, vertX1, vertY1, vertX2, vertY2, color);
    }
}

static auto processBatchEllipse(const JsonObject& cmd, uint16_t color) -> void {
    int16_t posX = getInt16(cmd, "x", DEFAULT_CENTER);
    int16_t posY = getInt16(cmd, "y", DEFAULT_CENTER);
    int16_t radiusX = getInt16(cmd, "rx", DEFAULT_SIZE_LARGE);
    int16_t radiusY = getInt16(cmd, "ry", DEFAULT_SIZE_MEDIUM);
    bool shouldFill = getBool(cmd, "fill", true);
    if (shouldFill) {
        DisplayManager::fillEllipse(posX, posY, radiusX, radiusY, color);
    } else {
        DisplayManager::drawEllipse(posX, posY, radiusX, radiusY, color);
    }
}

static auto processBatchRoundRect(const JsonObject& cmd, uint16_t color) -> void {
    int16_t posX = getInt16(cmd, "x", DEFAULT_POS);
    int16_t posY = getInt16(cmd, "y", DEFAULT_POS);
    int16_t width = getInt16(cmd, "w", DEFAULT_SIZE_LARGE);
    int16_t height = getInt16(cmd, "h", DEFAULT_SIZE_MEDIUM);
    int16_t radius = getInt16(cmd, "r", DEFAULT_CORNER_RADIUS);
    bool shouldFill = getBool(cmd, "fill", true);
    if (shouldFill) {
        DisplayManager::fillRoundRect(posX, posY, width, height, radius, color);
    } else {
        DisplayManager::drawRoundRect(posX, posY, width, height, radius, color);
    }
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
        sendErrorResponse(webserver, "invalid json");
        return;
    }

    JsonArray commands = doc["commands"].as<JsonArray>();
    int processed = 0;

    for (JsonObject cmd : commands) {
        String cmdType = cmd.containsKey("type") ? cmd["type"].as<String>() : "";
        uint16_t color = getColorFromJson(cmd);

        if (cmdType == "clear") {
            DisplayManager::fillScreen(color);
        } else if (cmdType == "rect") {
            processBatchRect(cmd, color);
        } else if (cmdType == "circle") {
            processBatchCircle(cmd, color);
        } else if (cmdType == "line") {
            processBatchLine(cmd, color);
        } else if (cmdType == "pixel") {
            processBatchPixel(cmd, color);
        } else if (cmdType == "text") {
            processBatchText(cmd, color);
        } else if (cmdType == "triangle") {
            processBatchTriangle(cmd, color);
        } else if (cmdType == "ellipse") {
            processBatchEllipse(cmd, color);
        } else if (cmdType == "roundrect") {
            processBatchRoundRect(cmd, color);
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