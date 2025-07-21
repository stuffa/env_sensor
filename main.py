
from PiicoDev_Unified import sleep_ms # cross-platform compatible sleep function
from PiicoDev_BME280  import PiicoDev_BME280
from PiicoDev_ENS160  import PiicoDev_ENS160
from nbiot            import NBIoT
from config           import Config
from ota_update       import OTAUpdate

import asyncio
import machine
import sys
import utils
import time
import io
import json


def wait_for_startup_interrupt():
    count = 5
    if debug: print(f"Wait for user interrupt ({count}) secs")
    while count:
        sleep_ms(1000)
        count -= 1


async def wdt_task():
    if debug: print('WDT task started') 

    interval = 1000    
    wdt    = machine.WDT(timeout = 8388) # Start the watchdog 8.388 seconds

    while True:
        wdt.feed()
        await asyncio.sleep_ms(interval)

#############################
#    main
#############################

# Slow down the clock to save power
machine.freq(48_000_000)

debug = False
if utils.console_connected():
    debug = True

net    = NBIoT()
uid    = utils.uid()       # The id sent to the mqtt server
env    = PiicoDev_BME280() # initialise the env sensor
air    = PiicoDev_ENS160() # initialise the aqi sensor
config = Config()

mqtt_base_topic = "sensors/circulait"
mqtt_server = "mqtt.at.martin.cc"
rails_server = "accelerate-advantage-b6d76071507e.herokuapp.com"

rc = machine.reset_cause()
rc_reason = "unknown"
if debug:
    print(f"Reset Code: {rc}")

try:
    # This is all about displaying the reason for a restart
    # and then recovering appropriately.
    # Depending on the reset reason, there is an opportunity
    # to do stuff that we need only for that particular startup case
#   DEEPESLEEP_RESET is not defined
#   if rc == machine.DEEPSLEEP_RESET:
#       rc_reason = "DeepSleepReset"
#       if debug:
#         print("DeepSleep Reset")

#   HARD_RESET is not defined
#   if rc == machine.HARD_RESET:
#       rc_reason = "HardReset"
#       if debug:
#           print("Hard Reset")

#   SOFT_RESET is not defined
#   elif rc == machine.SOFT_RESET:
#       rc_reason = "SoftReset"
#       if debug:
#           print("Soft Reset")
#           # allow time for a developer to stop the process for debugging
#           # before starting the watchdog
#           wait_for_startup_interrupt()

    if rc == machine.PWRON_RESET:
        rc_reason = "PowerOn"
        # allow time for a developer to stop the process for debugging
        # before starting the watchdog
        if debug:
            print("POWER_ON reset")
            wait_for_startup_interrupt()
            net.factory_reset()
            net.disable()
            time.sleep(3)
        
    #     if ota_update.update_available():
    #         if debug: print('OTA Update available')
    #         ota_update.pull_all()
    #         if debug: print('OTA Update Completed')
    #     else:
    #         if debug: print('No OTA update')


    elif rc == machine.WDT_RESET:
        rc_reason = "WatchDog"
        # allow time for a developer to stop the process for debugging
        # before starting the watchdog
        if debug:
            print("Watchdog Reset")
            wait_for_startup_interrupt()
        # send wdt packet to server
        # attempt a firmware update

    else:
        if debug:
            print("Unknown Reset Reason")
        pass


    
    # do stuff that we only do once-off at startup
    if net.enable():
        # get the configuration from the server and update the config object
#         net.dns_lookup(rails_server)  # this will force a wait for the dns
#         content = net.get_http(f"https://{rails_server}/", f"/api/sensors/{uid}")
#         if debug:
#             print(f"content: {content}")
# 
#         if content:
#             config.update(json.loads(content))
#             config.save()

        # send a start message
        ip = net.dns_lookup(mqtt_server)
        if ip:
            t = time.gmtime()
            topic = f"{mqtt_base_topic}/start"
            msg = {
                    "u": uid,
                    "v": config.get_version(),
                    "b": utils.get_vsys(),
                    "r": rc_reason,
                    "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5]),
            }
            net.send_mqtt(ip, topic, msg)
    
    net.disable()

    if debug:
        print("Polling task started")

    total_count = 0
    env_count = 0
    env_data = []

    while True:

        if env._device_present:
            if debug:
                print("taking an env sample")

            temp, pressure, humidity = env.values() # read all data from the sensor
            t = time.gmtime()
            
            data = {
                "t": temp,
                "p": pressure,
                "h": humidity,
                "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5]),
                "i": env_count
            }
            
            env_data.append(data)
            if debug: print(f"env: {data}")

        env_count += 1
        total_count += 1
        
        if env_count >= config.getVal('sample_count'):
            env_count = 0
            tvoc = {}
            
            if air._device_present:                
                if debug: print("Wait for sensor to be ready...")
                air.wakeup()
                
                time.sleep(config.getVal('tvoc_wait') * 60)
                
                if debug:
                    print("taking a tvoc sample")
            
                air.temperature = temp
                air.humidity    = humidity
                
                tvoc = air.tvoc
                eco2 = air.eco2
                aqi  = air.aqi
                t    = time.gmtime() # get time again as we had to wait for the heater, to heat up

                if debug:
                    print("deepsleep air")

                air.deepsleep()

                tvoc = {
                    "a": aqi.value,
                    "t": tvoc,
                    "e": eco2.value,
                    "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5])
                }

            if debug:
                print("Build message")

            t = time.gmtime()
            msg = {
                "u": uid,
                "i": total_count,
                "b": utils.get_vsys(),
                "e": env_data,
                "t": tvoc,
                "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5])
            }
            if debug:
                print(msg)

            topic = f"{mqtt_base_topic}/data"
    
            # TODO: If we don't succeed try again
            if net.enable():
                ip = net.dns_lookup(mqtt_server)
                msg["rssi"] = net.rssi()
                if ip:
                    net.send_mqtt(ip, topic, msg)
     
            net.disable()
            
            env_data = []
            tvoc     = {}

        if debug:
            print(f"sleeping for next sample. count: {total_count}")

        time.sleep(config.getVal('sample_interval') * 60)

except Exception as e:
    if net:
        buf = io.StringIO()
        sys.print_exception(e, buf)
        traceback_str = buf.getvalue()
        traceback_array = traceback_str.splitlines()
        t = time.gmtime()
        msg = {
            "u": uid,
            "v": config.get_version(),
            "t": type(e).__name__,
            "a": e.args,
            "tb": traceback_array,
            "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5]),
        }
        if debug:
            print(msg)
        
        topic = f"{mqtt_base_topic}/exception"
        
        net.disable()
        if net.enable():
            ip = net.dns_lookup(mqtt_server)
            if ip:
                net.send_mqtt(ip, topic, msg)
        net.disable()

    machine.reset()


# Start the tasks
#tasks = [
#     asyncio.create_task(ble.key_task()),
#     asyncio.create_task(ble.ssid_task()),
#     asyncio.create_task(ble.name_task()),
#     asyncio.create_task(ble.save_config_task()),
#     asyncio.create_task(ble.advertising_task()),
#    asyncio.create_task(wdt_task()),
#    asyncio.create_task(polling_task(config, station, nbiot)),
#]

# wait for them to complete
#asyncio.run( asyncio.gather(*tasks) )
