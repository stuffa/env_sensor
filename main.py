
from PiicoDev_Unified import sleep_ms # cross-platform compatible sleep function
from PiicoDev_BME280  import PiicoDev_BME280
from PiicoDev_ENS160  import PiicoDev_ENS160
# from ble_env_service  import BleEnvironment
# from display          import Display
from nbiot            import NB_IoT
from config           import Config
# from wifi             import WiFi

import asyncio
import machine
import sys
import utils
import ota_update
import time
import io
import json


def wait_for_startup_interrupt():
    count = 5
    print(f"Wait for user interrupt ({count}) secs")
    while count:
        sleep_ms(1000)
        count -= 1


async def wdt_task():
    print('WDT task started')

    interval = 1000    
    wdt    = machine.WDT(timeout = 8388) # Start the watchdog 8.388 seconds

    while True:
        wdt.feed()
        await asyncio.sleep_ms(interval)


def get_battery_level():
    # Setup pins
    machine.Pin(25, machine.Pin.OUT, value=1)  # Deselect Wi-Fi module
    machine.Pin(29, machine.Pin.IN, pull=None)  # Set VSYS ADC pin floating

    # VSYS measurement
    vsys_adc = machine.ADC(29)
    vsys = (vsys_adc.read_u16() / 65535) * 3 * 3.3
    
    print(f"Batt: {vsys}")

    return vsys

#############################
#    main
#############################

# Slow down the clock to save power
machine.freq(48_000_000)

try:
    # check if we have an NB_IoT device
    net = NB_IoT()
    uid = utils.uid()      # The id sent to the mqtt server
    env = PiicoDev_BME280() # initialise the env sensor
    air = PiicoDev_ENS160() # initialise the aqi sensor 
    config = Config()

    rc = machine.reset_cause()
    rc_reason = "unknown"
    print(f"Reset Code: {rc}")

    # DEEPESLEEP_RESET is not defined
#     if rc == machine.DEEPSLEEP_RESET:
#         print("DeepSleep Reset")
#         rc_reason = "DeepSleepReset"

    # HARD_RESET is not defined
#     if rc == machine.HARD_RESET:
#         print("Hard Reset")
#         rc_reason = "HardReset"

    if rc == machine.PWRON_RESET:
        print("POWER_ON reset")
        rc_reason = "PowerOn"
        # allow time for a developer to stop the process for debugging
        # before starting the watchdog
        if utils.console_connected():
            wait_for_startup_interrupt()
            # reset the network
            net.factory_reset()
        
    #     if ota_update.update_available():
    #         print('OTA Update available')
    #         ota_update.pull_all()
    #         print('OTA Update Completed')
    #     else:
    #         print('No OTA update')

    # SOFT_RESET is not defined
#     elif rc == machine.SOFT_RESET:
#         print("Soft Reset")
#         rc_reason = "SoftReset"
#         # allow time for a developer to stop the process for debugging
#         # before starting the watchdog
#         if utils.console_connected():
#             wait_for_startup_interrupt()

    elif rc == machine.WDT_RESET:
        print("Watchdog Reset")
        rc_reason = "WatchDog"
        # allow time for a developer to stop the process for debugging
        # before starting the watchdog
        if utils.console_connected():
            wait_for_startup_interrupt()
        # send wdt packet to server
        # attempt a firmware update
    
    else:
        print("Unknown Reset Reason")
        pass



    if net.enable():
        # do stuff that we only do once-off at start

        # upgrade
#         net.OTA_upgade()


        # get the configutaion from the server, and update the config object
        content = net.getHTTP("https://accelerate-advantage-b6d76071507e.herokuapp.com/", f"/api/sensors/{uid}")
        print(f"content: {content}")
        if content:
            config.update(json.loads(content))
            config.save

        # send a start message
        t = time.gmtime()
        topic = f'environment/{uid}/start'
        msg = {
                "u": uid,
                "n": config.getVal('name'),
                "b": get_battery_level(),
                "r": rc_reason,
                "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5]),

        }
        net.sendMQTT(topic, msg)
    net.disable()

    print("Polling task started")

    count = 0
    sample_count = 0
    env_data = []
    
    while True:
        print("taking an env sample")
        
        temp, pressure, humidity = env.values() # read all data from the sensor
        t = time.gmtime()
        
        data = {
            "t": temp,
            "p": pressure,
            "h": humidity,
            "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5]),
            "i": sample_count
        }
        
        env_data.append(data)
        print(f"env: {data}")

        sample_count += 1
        count += 1
        if (sample_count >= config.getVal('sample_count')):
            sample_count = 0
            
            print("Wait for sensor to be ready...")
            air.wakeup()
            
            time.sleep(config.getVal('tvoc_wait') * 60)
            
            print("taking a tvoc sample")
        
            air.temperature = temp
            air.humidity    = humidity
            
            tvoc = air.tvoc
            eco2 = air.eco2
            aqi  = air.aqi


            print("deepsleep air")
            air.deepsleep()
    
            tvoc = {
                "a": aqi.value,
                "t": tvoc,
                "e": eco2.value,
                "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5]),

            }

            t = time.gmtime()
            topic = f'environment/{uid}/data'

            print("Build message")
            msg = {
                "u": uid,
                "i": count,
                "n": config.getVal('name'),
                "b": get_battery_level(),
                "e": env_data,
                "t": tvoc
            }
            env_data = []
            
            print(msg)
            
            if net.enable():        
                net.sendMQTT(topic, msg)
     
            net.disable()
                    
        print(f"sleeping for next sample. count: {count}")
        time.sleep(config.getVal('sample_interval') * 60)

except Exception as e:
    if net:
        buf = io.StringIO()
        sys.print_exception(e, buf)
        traceback_str = buf.getvalue()
        traceback_array = traceback_str.splitlines()
        t = time.gmtime()
        msg = {
            "i": uid,
            "v": config.get_version(),
            "t": type(e).__name__,
            "a": e.args,
            "t":  traceback_array,
            "utc": "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5]),
        }
        
        topic = f"environment/{uid}/exception"
        
        net.disable()
        if net.enable():
            net.sendMQTT(topic, msg)
        net.disable()
                
        
    machine.reset()
#     sys.exit(-1)

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
