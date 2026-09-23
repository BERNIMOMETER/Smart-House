#pragma once

// Copy this file to firmware/config.h and fill in local network/broker settings.
// config.h is intentionally excluded from git.
#define WIFI_SSID "YOUR_WIFI_NAME"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define MQTT_HOST "YOUR_CLUSTER.s1.eu.hivemq.cloud"
#define MQTT_PORT 8883
#define MQTT_USER "YOUR_HIVEMQ_USERNAME"
#define MQTT_PASSWORD "YOUR_HIVEMQ_PASSWORD"
#define MQTT_CLIENT_ID "smarthouse-esp32-s3"
#define MQTT_TOPIC_PREFIX "smarthouse"

// Production requires TLS and certificate validation. Keep this set to 1 for
// HiveMQ Cloud. Set it to 0 only for an isolated local-development broker.
#define MQTT_TLS 1

#if MQTT_TLS
// Paste the PEM root CA that validates your HiveMQ Cloud cluster here. This
// certificate is public, but credentials above must remain private.
static const char MQTT_ROOT_CA[] = R"EOF(
-----BEGIN CERTIFICATE-----
PASTE_THE_HIVEMQ_CLOUD_ROOT_CA_CERTIFICATE_HERE
-----END CERTIFICATE-----
)EOF";

// TLS certificate validation needs a current clock. The ESP32 obtains it
// after joining Wi-Fi; allow outbound NTP access to this server.
#define NTP_SERVER "pool.ntp.org"
#endif
