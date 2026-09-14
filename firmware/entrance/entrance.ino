#include <WiFi.h>
#include <PubSubClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ESP32Servo.h>
#include "../config.h"

constexpr int LDR_PIN=34, PIR_PIN=27, LED_PIN=25, SERVO_PIN=26, SS_PIN=5, RST_PIN=22;
constexpr int LDR_DARK_THRESHOLD=1600, DOOR_OPEN_ANGLE=90, DOOR_CLOSED_ANGLE=0;
constexpr unsigned long DOOR_OPEN_MS=4000;
const char *BASE="smarthouse/entrance/";
WiFiClient wifiClient; PubSubClient mqtt(wifiClient); MFRC522 rfid(SS_PIN,RST_PIN); Servo door;
bool securityMode=false, alarm=false, outdoorLed=false, lightManual=false; unsigned long doorClosesAt=0,lastReport=0;

void pub(const char*d,const char*v){char t[72];snprintf(t,sizeof(t),"%s%s/state",BASE,d);mqtt.publish(t,v,true);} void pubEvent(const char*d,const char*v){char t[72];snprintf(t,sizeof(t),"%s%s/state",BASE,d);mqtt.publish(t,v,false);} void pubBool(const char*d,bool v){pub(d,v?"ON":"OFF");}
void setLed(bool on){outdoorLed=on;digitalWrite(LED_PIN,on);pubBool("outdoor_led",on);} void setAlarm(bool on){alarm=on;pubBool("alarm",on);}
void openDoor(){door.write(DOOR_OPEN_ANGLE);doorClosesAt=millis()+DOOR_OPEN_MS;pub("door","OPEN");}
void onMessage(char*topic,byte*payload,unsigned int len){String v;for(unsigned int i=0;i<len;i++)v+=(char)payload[i];String t(topic);if(t=="smarthouse/system/security_mode/set"){securityMode=v=="ON";if(!securityMode)setAlarm(false);pub("security_mode",securityMode?"ON":"OFF");}else if(t=="smarthouse/entrance/outdoor_led/set"){if(v=="AUTO")lightManual=false;else{lightManual=true;setLed(v=="ON");}}else if(t=="smarthouse/entrance/door/set"&&v=="OPEN")openDoor();}
void connectMqtt(){while(!mqtt.connected()){if(mqtt.connect("entrance",MQTT_USER,MQTT_PASSWORD)){mqtt.subscribe("smarthouse/system/security_mode/set");mqtt.subscribe("smarthouse/entrance/outdoor_led/set");mqtt.subscribe("smarthouse/entrance/door/set");pubBool("outdoor_led",outdoorLed);pubBool("alarm",alarm);pub("door","CLOSED");}else delay(3000);}}
bool allowedTag(String id){return id=="REPLACE_WITH_AUTHORISED_UID";} // Store/tag-authorize server-side in a production version.
void checkNfc(){if(!rfid.PICC_IsNewCardPresent()||!rfid.PICC_ReadCardSerial())return;String id="";for(byte i=0;i<rfid.uid.size;i++){if(rfid.uid.uidByte[i]<16)id+="0";id+=String(rfid.uid.uidByte[i],HEX);}bool granted=allowedTag(id);if(granted)openDoor();char p[140];snprintf(p,sizeof(p),"{\"tag_id\":\"%s\",\"granted\":%s}",id.c_str(),granted?"true":"false");pubEvent("nfc",p);rfid.PICC_HaltA();}
void setup(){pinMode(PIR_PIN,INPUT);pinMode(LED_PIN,OUTPUT);door.attach(SERVO_PIN);door.write(DOOR_CLOSED_ANGLE);SPI.begin();rfid.PCD_Init();WiFi.begin(WIFI_SSID,WIFI_PASSWORD);while(WiFi.status()!=WL_CONNECTED)delay(500);mqtt.setServer(MQTT_HOST,MQTT_PORT);mqtt.setCallback(onMessage);}
void loop(){if(!mqtt.connected())connectMqtt();mqtt.loop();if(doorClosesAt&&millis()>=doorClosesAt){door.write(DOOR_CLOSED_ANGLE);doorClosesAt=0;pub("door","CLOSED");}if(securityMode&&digitalRead(PIR_PIN)==HIGH&&!alarm){setAlarm(true);pubBool("pir",true);}int ldr=analogRead(LDR_PIN);if(!lightManual && ((ldr<LDR_DARK_THRESHOLD)!=outdoorLed))setLed(ldr<LDR_DARK_THRESHOLD);if(millis()-lastReport>10000){lastReport=millis();char p[48];snprintf(p,sizeof(p),"{\"raw\":%d}",ldr);pub("ldr",p);}checkNfc();}
