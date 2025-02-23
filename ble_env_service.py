import sys
import asyncio
import aioble
import bluetooth
import json
import utils

from micropython import const


_DEVICE_INFO_UUID = bluetooth.UUID(0x180A)
_MANUFACTURER_ID      = const(0x2A29)
_MODEL_NUMBER_ID      = const(0x2A24)
_SERIAL_NUMBER_ID     = const(0x2A25)
_HARDWARE_REVISION_ID = const(0x2A26)
_BLE_VERSION_ID       = const(0x2A28)


_ENV_SENSOR_INFO_UUID = bluetooth.UUID(0x181A)
_TEMPERATURE_ID = const(0x2A6E)
_HUMIDITY_ID    = const(0x2A6F)
_PRESSURE_ID    = const(0x2A6D)


_WIFI_SETTINGS_UUID = bluetooth.UUID("21c04d09-c884-4af1-96a9-52e4e4ba195b")
_WIFI_NAME_ID   = bluetooth.UUID("1e500043-6b31-4a3d-b91e-025f92ca9762")
_WIFI_SSID_ID   = bluetooth.UUID("1e500043-6b31-4a3d-b91e-025f92ca9763")
_WIFI_KEY_ID    = bluetooth.UUID("1e500043-6b31-4a3d-b91e-025f92ca9764")
_WIFI_STATUS_ID = bluetooth.UUID("1e500043-6b31-4a3d-b91e-025f92ca9765")
_WIFI_SAVE_ID   = bluetooth.UUID("1e500043-6b31-4a3d-b91e-025f92ca9766")

# this is used as the appearance in the ble advertisements - not sure what that does
_GENERIC_THERMOMETER = const(768)
_SERVICES = [_DEVICE_INFO_UUID, _ENV_SENSOR_INFO_UUID, _WIFI_SETTINGS_UUID]
_MANUFACTURER = b"martin.cc"
_MODEL = "TPH-1.0"

# Advertising frequency
_ADV_INTERVAL_MS = 5_000


class BleEnvironment():
    def __init__(self, name='PicoSensors'):

        self._key = ""
        
        print("Initialising BLE Services")

        self._device_info = aioble.Service(_DEVICE_INFO_UUID)
        self._manufacturer_char = aioble.Characteristic(self._device_info, bluetooth.UUID(_MANUFACTURER_ID), read=True, initial=_MANUFACTURER)
        self._model_char        = aioble.Characteristic(self._device_info, bluetooth.UUID(_MODEL_NUMBER_ID), read=True, initial="THPAQ-1.0")
#         aioble.Characteristic(self._device_info, bluetooth.UUID(_SERIAL_NUMBER_ID),     read=True, initial=utils.uid())
#         aioble.Characteristic(self.device_info, bluetooth.UUID(_HARDWARE_REVISION_ID), read=True, initial=str(sys.version))
#         aioble.Characteristic(self.device_info, bluetooth.UUID(_BLE_VERSION_ID),       read=True, initial="1.0")
        
        self._manufacturer_char.write(_MANUFACTURER)
        self._model_char.write(_MODEL)
        
        self._sensor_info = aioble.Service(_ENV_SENSOR_INFO_UUID)
        self._temperature_char = aioble.Characteristic(self._sensor_info, bluetooth.UUID(_TEMPERATURE_ID), read=True, notify=True)
        self._humidity_char   = aioble.Characteristic(self._sensor_info, bluetooth.UUID(_HUMIDITY_ID),   read=True, notify=True)
        self._pressure_char   = aioble.Characteristic(self._sensor_info, bluetooth.UUID(_PRESSURE_ID),   read=True, notify=True)
        
        self._wifi_info = aioble.Service(_WIFI_SETTINGS_UUID)
        self._name_char   = aioble.Characteristic(self._wifi_info, _WIFI_NAME_ID,   read=True,  write=True,  capture=False)
        self._ssid_char   = aioble.Characteristic(self._wifi_info, _WIFI_SSID_ID,   read=True,  write=True,  capture=False)
        self._key_char    = aioble.Characteristic(self._wifi_info, _WIFI_KEY_ID,    read=False, write=True,  capture=False)
#         self._status_char = aioble.Characteristic(self._wifi_info, _WIFI_STATUS_ID, read=True,  write=False, capture=False)
        self._save_char   = aioble.Characteristic(self._wifi_info, _WIFI_SAVE_ID,   read=False, write=True,  capture=True)
        
        try:
            with open("config.json", "rt") as f:
                config = json.load(f)
        except:
            config = { 'name': name, 'ssid': '', 'key': '' }
        
        
        if config["name"]:
            self._name_char.write(config["name"])
        if config["ssid"]:
            self._ssid_char.write(config["ssid"])
        if config["key"]:
            self._key = config["key"]
            
        self.update_temperature(0)
        self.update_humidity(0)
        self.update_pressure(0)

        print('registering services')
        aioble.register_services(self._device_info, self._sensor_info, self._wifi_info)


    def wifi_key(self):
        return self._key
    
    
    def wifi_ssid(self):
        return self._ssid_char.read().decode("utf-8")


    def name(self):
        return self._name_char.read().decode("utf-8")


    def update_temperature(self, temp):
        self._temperature_char.write(int(temp * 100).to_bytes(2, 'little'), send_update=True)


    def update_humidity(self, humidity):
        self._humidity_char.write(int(humidity*100).to_bytes(2, 'little'), send_update=True)


    def update_pressure(self, pressure):    
        self._pressure_char.write(int(pressure*10).to_bytes(4, 'little'), send_update=True)
        
        
    def save_settings(self):
            print("making config")
            config = {
                "name": self._name_char.read().decode("utf-8"),
                "ssid": self._ssid_char.read().decode("utf-8"),
                "key": self._key
            }
            print("New Config: " + str(config))
            
            with open("config.json", "wt") as f:
                json.dump(config, f)
        
# 
#     async def key_task(self):
#         print("Starting key task")
#         while True:
#             try:
#                 connection, data = await self._key_char.written()
#                 self._key = data.decode("utf-8")
#                 self._key_char.write("")  # clear the key from ble
#                 print("Key = " + self._key )
#                 self.save_settings()
#                     
#             except asyncio.TimeoutError:
#                 continue
# 
#             except Exception as err:
#                 sys.print_exception(err)
#                 continue
# 
# 
#     async def ssid_task(self):
#         print("Starting ssid task")
#         while True:
#             try:
#                 connection, data = await self._ssid_char.written()
#                 self.save_settings()
#                     
#             except asyncio.TimeoutError:
#                 continue
# 
#             except Exception as err:
#                 sys.print_exception(err)
#                 continue
# 
#     async def name_task(self):
#         print("Starting name task")
#         while True:
#             try:
#                 connection, data = await self._name_char.written()
#                 self.save_settings()
#                     
#             except asyncio.TimeoutError:
#                 continue
# 
#             except Exception as err:
#                 sys.print_exception(err)
#                 continue

    async def save_config_task(self):
        print("Starting save_config task")
        while True:
            try:
                connection, data = await self._save_char.written()
                self._save_char.write(0)    
                self.save_settings()
                    
            except asyncio.TimeoutError:
                continue

            except Exception as err:
                sys.print_exception(err)
                continue


    async def advertising_task(self):
        print("Advertising task started")
        while True:
            connection = await aioble.advertise(
                _ADV_INTERVAL_MS,
                name=self.name(),
                services=_SERVICES,
                appearance=_GENERIC_THERMOMETER,
                manufacturer=(0xabcd, _MANUFACTURER),
            )
            print("Connection from", connection.device)

