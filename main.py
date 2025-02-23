
from PiicoDev_Unified import sleep_ms # cross-platform compatible sleep function
from PiicoDev_BME280 import PiicoDev_BME280
from PiicoDev_ENS160 import PiicoDev_ENS160
from lib.umqtt.simple import MQTTClient
from ble_env_service import BleEnvironment
from display import Display

import asyncio
import network
import machine
import ubinascii
import json
import sys
import utils
import ota_update
import ntptime
import time

def display_data(display, temp, pressure, humidity, aqi, tvoc, eco2):
    display.clear()
    display.add("Temp:" + utils.rjust(str(round(temp)), 9) + " C")
    display.add("RH:" + utils.rjust(str(round(humidity)), 11) + " %")
    display.add("kPa:" + utils.rjust(str(round(pressure / 1000, 1)), 12))
    display.add("AQI:" + utils.rjust(utils.titleise(aqi.rating), 12))
    display.add("TVOC:" + utils.rjust(str(round(tvoc)), 7) + " ppb")
    display.add("eCO2:" + utils.rjust(str(round(eco2.value)), 7) + " ppm")
    display.show()


def restart(display):
  print('Restarting...')
  try:
      display.clear()
      display.add("Restarting...")
      display.show()

  finally:    
      machine.reset()
    

def wait_for_startup_interrupt(display):
    print("Wait for user interrupt")
    count = 5
    row = display.add("Interrupt......" + str(count))
    display.show()
    while count:
        sleep_ms(1000)
        count -= 1
        display.put(row, "Interrupt......" + str(count))
        display.show()

    display.put(row, "Interrupt.....OK")
    display.show()
 
 
async def connect_to_wifi(display, ble, station):

    row = display.add("WiFi..........??")
    display.show()
    print('Connecting to WiFi - ' + ble.wifi_ssid())

    while not station.isconnected():
        if station.active():
            station.active(False)
        
        station.active(True)
        
        print("Connecting to: " + ble.wifi_ssid() +":" + ble.wifi_key()) 
        station.connect(ble.wifi_ssid(), ble.wifi_key())
        # wait max 10 seconds to connect, before trying again
        count = 100
        while (count > 0) and (station.isconnected() == False):
            count -= 1
            await asyncio.sleep_ms(100)

    # We only get here is we successfully connected to Wi-Fi
    display.put(row, "WiFi..........OK")
    display.show()
    print("Wifi Connected OK")
    print(station.ifconfig())


def get_utc_time(display):
    row = display.add("NTP...........??")
    display.show()
    ntptime.settime()
    t = time.gmtime()
    print("Date: {}-{:02d}-{:02d}, Time: {:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4]))
    display.put(row, "NTP...........OK")
    display.show()


def connect_to_mqtt(display):    
    print('Connecting to MQTT')

    row = display.add("MQTT..........??")
    display.show()

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



def mqtt_publish_environment(mqtt_client, uid, name, temp, pressure, humidity, aqi, tvoc, eco2):
    t = time.gmtime()
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


async def polling_task(display, ble, station):
    
    print("Polling task started")
    
    uid  = utils.uid()      # The id sent to the mqtt server
    env = PiicoDev_BME280() # initialise the env sensor
    air = PiicoDev_ENS160() # initialise the aqi sensor 

    await connect_to_wifi(display, ble, station)

    get_utc_time(display)
    
    row = display.add('OTA Update....??')
    display.show()
    if ota_update.update_available():
        print('OTA Update available')
        display.put(row, 'OTA Update...YES')
        display.show()
        ota_update.pull_all()
        display.put(row, 'OTA Update....OK')
        print('OTA Update Completed')
    else:
        display.put(row, 'OTA Update....NO')
        print('No OTA update')
    display.show()    
    
    # connect to the mqtt server
    mqtt_client = connect_to_mqtt(display)

#     Allow 2 secs before we clear the screen
    sleep_ms(2000)
    display.clear()
    display.show()
    
    while True:
        try:
            temp, pressure, humidity = env.values() # read all data from the sensor

            air.temperature = temp
            air.humidity    = humidity
            
            tvoc = air.tvoc
            eco2 = air.eco2
            aqi  = air.aqi
        
#           print('---------------------------------------------')
#           print('    Temp: ' + str(round(temp)) + " °C, ")
#           print('Pressure: ' + str(round(pressure/1000))+" kPa, ")
#           print('Humidity: ' + str(round(humidity)) + " %")
#           print('     AQI: ' + str(aqi.value) +  ' [' + str(aqi.rating) +']')
#           print('    TVOC: ' + str(tvoc) + ' ppb')
#           print('    eCO2: ' + str(eco2.value) + ' ppm [' + str(eco2.rating) +']')
#           print('  Status: ' + str(air.status_validity_flag) + ' [' + air.operation +']')

            display_data(display, temp, pressure, humidity, aqi, tvoc, eco2)
            mqtt_publish_environment(mqtt_client, uid, ble.name(), temp, pressure, humidity, aqi, tvoc, eco2)
            ble.update_temperature(temp)
            ble.update_humidity(humidity)
            ble.update_pressure(pressure)
       
        except Exception as err: 
            sys.print_exception(err)  
            restart(display)    
        
#         machine.deepsleep(5000)
        await asyncio.sleep_ms(5000)

async def blink_task(station):
    print('blink task started')
    
    led    = machine.Pin("LED", machine.Pin.OUT)
    toggle = True
#     wdt    = machine.WDT(timeout = 8388) # Start the watchdog 8.388 seconds
    
    while True:
#         wdt.feed()
        toggle = not toggle
        led.value(toggle)
        blink = 500 if station.isconnected() else 250            
        await asyncio.sleep_ms(blink)
        

        
#############################
#    main
#############################

# first initialize the display so we can display progres
display = Display()
display.clear()
display.show()

# start the Wi-Fi
station = network.WLAN(network.STA_IF)


if utils.console_connected():
    wait_for_startup_interrupt(display)
    

# create the object we will be using
ble = BleEnvironment()

# rc = machine.reset_cause()
# if (rc == machine.PWRON_RESET):
    # allow time for a developer to stop the process for debugging
    # before starting the watchdog
    # attempt a firmware update



# Start the tasks
tasks = [
#     asyncio.create_task(ble.key_task()),
#     asyncio.create_task(ble.ssid_task()),
#     asyncio.create_task(ble.name_task()),
    asyncio.create_task(ble.save_config_task()),
    asyncio.create_task(ble.advertising_task()),
    asyncio.create_task(blink_task(station)),
    asyncio.create_task(polling_task(display, ble, station)),
]

# wait for them to complete
asyncio.run( asyncio.gather(*tasks) )
print('Finished')