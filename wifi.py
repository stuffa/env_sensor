from lib.umqtt.simple import MQTTClient

import asyncio
import network
import ntptime

class WiFi:
    
    _station=None
    _config=None
    
    def __init__(self, config):
        self._config = config
        self._station = network.WLAN(network.STA_IF)
        

    def enable(self):
        print('Connecting to WiFi - ' + self._config.wifi_ssid)
        while not self._station.isconnected():
            if self._station.active():
                self._station.active(False)

            self._station.active(True)

            self._station.connect(self._config.wifi_ssid(), self._config.wifi_key())
            # wait max 10 seconds to connect, before trying again
            count = 100
            while (count > 0) and (self._station.isconnected() == False):
                count -= 1
                await asyncio.sleep_ms(100)

        # We only get here is we successfully connected to Wi-Fi
        print("Wifi Connected OK")
        print(station.ifconfig())


    def disconnect(self):
        if self._station:
            if self._station.isconnected():
                self._station.disconnect()
            if self._station.active():
                self._station.active(False)
            self._station.deinit()
            self._station = None
            return True
        return False


    def set_utc_time(self):
        print('Getting NTP Date/Time') 
        try:
            ntptime.settime()
        except:
            print("Unable to reach the NTP server")
            return False
        t = time.gmtime()
        print("NTP: Date: {}-{:02d}-{:02d}, Time: {:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4]))
        retrun True

    def _connect_to_mqtt(self, server, port, user, password):    
        print('Connecting to MQTT')

        # mqtt server
        mqtt_server = 'mqtt.martin.cc'
        mqtt_user = b'cmartin'
        mqtt_pass = b'a324d2b3f5eef7aff428d038dcea8e80'
        mqtt_keepalive = 20

        client_id = ubinascii.hexlify(machine.unique_id())

        try:
            mqtt_client = MQTTClient(client_id, mqtt_server, user=mqtt_user, password=mqtt_pass, keepalive=mqtt_keepalive)
            mqtt_client.connect()
            print('Connected to %s MQTT broker' % mqtt_server)
            display.put(row, "MQTT..........OK")
            display.show()
            return mqtt_client
        except:
            restart(display)


    def sendMQTT(self, cid, name, json_message):
        server = mqtt.martin.cc
        port = 
        self._connect_to_mqtt(server, port, user, password)
        msg = {
            "id": uid,
            "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5]),
            "name": name,
            "temp": temp,
            "pressure": pressure,
            "humidity": humidity,
            "aqi_value": aqi.value,
            "aqi_rating": aqi.rating,
            "tvoc_value": tvoc,
            "eco2_value": eco2.value,
            "eco2_rating": eco2.rating
        }
        mqtt_client.publish( 'environment/' + uid, json.dumps(msg), retain=True)

    def factory_reset(self):
        return True

