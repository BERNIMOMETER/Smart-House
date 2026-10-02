HARDWARE REQUIREMENT
NOTE: Buzzer (Only one buzzer throughout the house, for alert system when the mq2 detects a smoke, it will trigger the buzzer either when the security mode is on or off. The buzzer is also used for security mode when the PIR detected something).
	For the PIR sensor, when the system is in security mode on, it will trigger the buzzer when it detects something.

House Places:
Kitchen same room to the Living room:
	Sensor:
MQ2 Sensor - Smoke Sensor, it will always read for 		
	Actuator:
Fan - it will suck out smoke (REMOVE FROM PROTOTYPE)

Living Room same room to the Kitchen:
	Sensor:
		PIR - Motion Sensor 
	Actuator:
		LED (RELAY CH-3)
		Buzzer (General Purpose)
		
Bedroom:
	Sensor:
		Dht11
	Actuator:	
		Fan for high temperature (RELAY CH-1) (NO PWM ON AND OFF ONLY)
		LED	(RELAY CH-4)

Entrance (OUTDOOR): 
	Sensor:
		LDR sensor
		PIR Sensor (Alarm system)
		NFC Reader (For door entrance)
	Actuator:
		Servo Motor
		LED (RELAY CH-2)

RELAY 4CH:
	CH1: BEDROOM LED
	CH2: LIVING ROOM AND KITCHEN LED
	CH3: ENTRANCE/OUTDOOR LIGHTS
	CH4: BEDROOM FAN

TOTAL SENSOR & ACTUATOR USED:

Sensors:
1. MQ2 smoke sensor - 1
2. PIR motion sensors - 1 (entrance only)
3. DHT11 temperature sensor - 1
5. NFC reader - 1

Total sensors: 4

Actuators:
1. LED lights - 3 (bedroom, living room/kitchen, and entrance/outdoor)
2. Bedroom fan - 1 (relay channel 4)
3. Buzzer - 1
4. Servo motor - 1

Total actuators: 6

Total sensors and actuators: 10



SOFTWARE REQUIREMENT
Stack:
	Django (Backend, Frontend)
	Database: sqlite
	Design: Tailwind CSS
	C++ for esp32
	MQTT
	PythonAnywhere for web hosting and database storage

Security Mode:
Home security:
Trigger: NFC Reader
Action: Open Door(Servo)
Remote:
	Open Door
Audit NFC Log(Write, Read)
Security Alarm:
	Trigger: PIR Sensors
	Action: Buzzer
	Remote: Status(Read)

Fire Alert (alert system):
	Trigger: MQ2 Sensor (smoke), 
Action: Buzzer when smoke detected
	Remote: IOT website Status(Read)

Temperature Regulation(Bedroom):
Trigger: DHT11
Action: Fan
Remote: 
IOT website 
status:DHT11(Read)
		status:FAN(Write, Boolean)

Light Control:
	Outdoor:
	Trigger:
IOT website
LDR Sensor
Action: Set Light
	Remote: IOT Website Status(Read, Set).
Indoor(Living Room):
	Trigger: IOT website
	Action: Set Light
	Remote: IOT website (read, set), can be on of off the LED light in the living room

Indoor(Bedroom):
	Trigger: IOT website
	Action: Set Light
	Remote: IOT website (read, set), can be on of off the LED light in the bedroom



