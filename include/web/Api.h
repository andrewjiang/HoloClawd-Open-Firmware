#ifndef API_H
#define API_H

#include "web/Webserver.h"

void registerApiEndpoints(Webserver* webserver);
void handleOtaUpload(Webserver* webserver, int mode);
void handleOtaFinished(Webserver* webserver);
void handleReboot(Webserver* webserver);

void handleGifUpload(Webserver* webserver);
void handleListGifs(Webserver* webserver);
void handlePlayGif(Webserver* webserver);
void handleStopGif(Webserver* webserver);

void handleWifiScan(Webserver* webserver);
void handleWifiConnect(Webserver* webserver);
void handleWifiStatus(Webserver* webserver);

// Drawing API endpoints
void handleDrawClear(Webserver* webserver);
void handleDrawText(Webserver* webserver);
void handleDrawRect(Webserver* webserver);
void handleDrawCircle(Webserver* webserver);
void handleDrawLine(Webserver* webserver);
void handleDrawPixel(Webserver* webserver);
void handleDrawTriangle(Webserver* webserver);
void handleDrawEllipse(Webserver* webserver);
void handleDrawRoundRect(Webserver* webserver);
void handleDrawBatch(Webserver* webserver);

#endif  // API_H
