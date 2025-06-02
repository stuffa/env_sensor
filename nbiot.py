import time
import ubinascii
import sys
import json
import machine

class NbiotCommandError(Exception):
    def __init__(self, message, resp=None):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        # Add the responce data
        self.resp = resp
        
class NbiotCommandTimeout(Exception):
    def __init__(self, message, resp=None):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        # Add the responce data
        self.resp = resp


class NB_IoT:

    nbiotEnablePin = 14  # The pico pin connected to enable on the NB-IoT chip
    nbiotEnable = None   # This is the pin Opject that holds the PinState   

    uartPort = 0         # The pico UART used to communicate with the NB-IoT chip 
    baudRate = 115200
    uart = None          # The uart object
    

    keepalive_interval = 600
    clean_session = 1
    will_flag = 0
    will_options = None
    qos = 1
    retained = 1
    dup = 0
    user = "mimos"
    password = "efd73d953f20838073a7a5b17aaad315"

    apn = "telstra.internet"
    
    enabled = False
    client_id = None
    ip_address = None
    cid = None
    mqtt_id = None


    def __init__(self):
        # Timeout is in (ms)
        self.uart = machine.UART(self.uartPort, self.baudRate, bits=8, parity=None, stop=1, timeout=1000)
        self.nbiotEnable = machine.Pin(self.nbiotEnablePin, machine.Pin.OUT)
        self.client_id = ubinascii.hexlify(machine.unique_id())


    def enable(self):
        print('#### NB-IoT Enable')
        self.wakeup()    # enable the chip

        if self.enabled:
            print("ERROR: enable() reentered - calling disable()")
            self.disable()
        
        try:
            print("Checking NB-IoT chip access")
            self.waitFor("+CPIN:")            
            time.sleep(1)                    

#             resp = self.sendCMD("AT+CMEE=2", comment="Enable verbose error output") # 0=disable, 1. numeric, 2=verbose

            # Wait for the DataPacket network to be ready
            print("Wait for the LTE network to be ready...")
            retry = 10
            while retry:
                resp = self.sendCMD("AT+CEREG?", "Check Network Status")
                data = self.parseFor("+CEREG:", resp)
                state = None

                if data:
                    state = data.split(",")[1]

                if state == "1": # 1: Registered to home network
                    print(f"Network status: {state} = Registered")
                    break

                elif state == "2": # seaching for Operator 
                    print(f"Network status: {state} = Searching")
                    time.sleep(3)

                elif state == "5": # 5: Roaming
                    print(f"Network status: {state} = Roaming")
                    break

                retry -= 1

            if not retry:
                print("Unable to connect to the EPS network")
                return False

            # Wait for PDP to be activated 
            print("Wait for activation...")
            retry = 10
            while retry:    
                # AT+CGACT PDP Context Activate or Deactivate
                resp = self.sendCMD("AT+CGACT?", comment="Get the PDP activated state")
                if  resp:                
                    result = self.parseFor("+CGACT:", resp)
                    if result:                
                        self.cid, state = result.split(",")
                        if state == "1":
                            print(f'cid: {self.cid}')
                            break

                retry =- 1
                time.sleep(3)

            if not retry:
                print("Unable to activate to the PDP")
                return False

            # Wait for IP address allocation
#             retry = 10
#             while True:
#                 resp = self.sendCMD(f'AT+CGCONTRDP={self.cid}', comment="Get the IP address assigned")
#                 data = self.parseFor("+CGCONTRDP:", resp)
#                 if data:
#                     self.ip_address = data.split(",")[3]
#                     if self.ip_address:
#                         print(f'IP Address" {self.ip_address}')
#                         break
#                     
#                 retry -= 1
#                 time.sleep(3)
#                 
#             if not retry:
#                 print("Unable to find IP address")
#                 return False

        except (NbiotCommandError, NbiotCommandTimeout) as e:
            self.cid = None
            self.ipaddress = None
            return False

        self.enabled = True
        return True


    def disable(self):
        print('#### NB-IoT Disable')
        try:
            if self.enabled:
                resp = self.sendCMD('AT+CGATT=0', comment="Disconnect")
            else:
                print("Already Disabled")
        except (NbiotCommandError, NbiotCommandTimeout) as e:
            pass

        finally:
            self.enabled = False
            self.gotoSleep()


    def factory_reset(self):
        print('#### NB-IoT Factory Reset')

        self.wakeup()    
        print("Checking NB-IoT chip access")
        self.waitFor("+CPIN:")
        self.waitForAT()

        try:
            resp = self.sendCMD("AT&F", "Reset NB-IoT NVRAM")
#             resp = self.sendCMD("AT&W", "Save Factory settings")
        except NbiotCommandError as e:
            return False

        time.sleep(1)

#         # there is no "OK" reply from the reset command
#         #so dont use sendCMD()
#         print("Rebooting NB-IoT...")
#         self.uart.write(('AT+CRESET\r\n').encode())
#         print ("Wait for Reboot to complete")
#         self.waitFor("+CPIN:")
        self.gotoSleep()
        self.enabled = False

        return True

#    def sendMQTT(self, topic, jsonMessage, server="mqtt.martin.cc", port=1883, version=4):    
    def sendMQTT(self, topic, jsonMessage, server="170.64.133.67", port=1883, version=4):
        print('#### NB-IoT MQTT Send')

        mqtt_delay = 1
        retry_cnt = 10

        while retry_cnt:
            mqtt_id = None
            retry_cnt -= 1
            try:
                # Create a new conection
                resp = self.sendCMD(f'AT+CMQNEW="{server}",{port},12000,1024', comment="Create an MQTT client")
                result = self.parseFor("+CMQNEW:", resp)
                if result:
                    mqtt_id = self.parseFor("+CMQNEW:", resp)
                    print (f"mqtt_id: {mqtt_id}")
                else:
                    self._disconnectMQTT(mqtt_id)
                    continue

                time.sleep(mqtt_delay)

                # Open a connection to the server
                # This may not connect connect - ie: timeout
                command = f'AT+CMQCON={mqtt_id},{version},"{self.client_id}",{self.keepalive_interval},{self.clean_session},{self.will_flag},"{self.user}","{self.password}"'
                resp = self.sendCMD(command, comment="Connect to the MQTT server" )
                # Timeout and Error will raise and exceptions
                # if we get here we got an OK    

                time.sleep(mqtt_delay)

                # add extra data to the payload
                jsonMessage['rssi'] = self.rssi()
                payload = json.dumps(jsonMessage).encode().hex()
                length = len(payload)

                # send the message to the mqtt server
                command = f'AT+CMQPUB={mqtt_id},"{topic}",{self.qos},{self.retained},{self.dup},{length},"{payload}"'
                resp = self.sendCMD(command, comment="Send MQTT message")
                # Timout and Error will both generate exceptions
                # if we get here we have received OK

                # TODO - subscribe and wait for the message to be sent back

                self._disconnectMQTT(mqtt_id) 
                return True

            except (NbiotCommandError, NbiotCommandTimeout):
                self._disconnectMQTT(mqtt_id)
                continue                

        # Exit due to to many retries
        return False
    
    
    def sendHTTP(self, path, jsonMessage, server="mqtt.mqrtin.cc", port=80):
        print('#### NB-IoT HTTP Send')
        try:
            resp = self.sendCMD(f'AT+CHTTPCREATE="http://{server}:{pot}/"', "New HTTP instance") 
            http_id = parseFor('+CHTTPCREAT:', resp)
            if not http_id:
                print ("No http_id")
                return False 
            print(f'http_id: {http_id}')
                
            resp = self.sendCMD(f'AT+CHTTPCON={http_id}', "Connect to HTTP server") 
            
            time.sleep(3)
            
            header = None
            content_type = "application/json"
            payload = json.dumps(jsonMessage).encode().hex()
            
            resp = self.sendCMD(f'AT+CHTTPSEND={http_id},2,"{path}",{header},"{content_type}",{payload}', "Send POST request") 

        except (NbiotCommandError, NbiotCommandTimeout) as e:
            return False
        
        return True
    
    def checkSettings(self):
        print('#### NB-IoT Check Settings')
        try:
            self.sendCMD('AT+CREVHEX?', "Data Mode 0:Raw 1:Binary")
            self.sendCMD('AT+CFUN?',    "Radio Functionality 0:Off 1:Full")
            self.sendCMD('AT+COPS?',    "Operator Selector")
            self.sendCMD('AT+CGATT?',   "Network attachment")
            self.sendCMD('AT+CGDCONT?', "PDP context")
            self.sendCMD('AT+CEREG?',   "Network Status")
            self.sendCMD('AT+CSQ',      "Received Signal Strength")
            self.sendCMD('AT+CGACT?',   "Get the cid")
            self.sendCMD('AT+CGCONTRDP=',"Get the IP addresses assigned")
            self.sendCMD('AT+CMQNEW?',  "Get the MQTT clients")
            self.sendCMD('AT+CMQCON?',  "Get the MQTT connections")

        except (NbiotCommandError, NbiotCommandTimeout) as e:
            pass
        
        return True
    
    def updateFirmware(self):
        print('#### NB-IoT Firmware Update')
        try:
            resp = self.sendCMD("AT+CGMR")
            print(f"Current firmware: {resp[1]}")
            resp = self.sendCMD("AT+CFOTA=1", "Start Firmware update")

        except (NbiotCommandError, NbiotCommandTimeout) as e:
            return False
        
        while True:
            stats, data = self.readUart()
            print(data)
            result = self.parseFor("+CFOTA:", data)
            if result == "No update package":
                print("Error: No update package")
                return False
            if result == "Update successfully":
                print(sucess)
                break
            
        try:
            resp = self.sendCMD("AT+CFOTA=4", "Save Update")
            print(f"Current firmware: {resp[1]}")
            resp = self.sendCMD("AT+CFOTA=1", "Start Firmware update")
        except (NbiotCommandError, NbiotCommandTimeout) as e:
            return False


    def getHTTP(self, host, path):
        content = None
        try:
            resp = self.sendCMD(f'AT+CHTTPCREATE="{host}"', f"HTTP create {host}")
            http_id = self.parseFor("+CHTTPCREATE:", resp)
            if not http_id: return False
            
            self.sendCMD(f'AT+CHTTPCON={http_id}', "HTTP connect")
            self.sendCMD(f'AT+CHTTPSEND={http_id},0,"{path}"', f"HTTP Get {path}")
            client_id, code, length, *rubbish = self.waitFor("+CHTTPNMIH:").split(',')
            if client_id == http_id and code == "200":
                client_id, flag, t_len, c_len, content_hex = self.waitFor("+CHTTPNMIC:").split(',')
                content = bytes.fromhex(content_hex).decode('utf-8')     
            self.sendCMD(f'AT+CHTTPDISCON={http_id}', "Disconnect the HTTP socket" ) 
            self.sendCMD(f'AT+CHTTPDESTROY={http_id}', "Destroy the host config") 
            
        except (NbiotCommandError, NbiotCommandTimeout) as e:
            return None
        
        return content
    
    
##################################################################

    def _disconnectMQTT(self, mqtt_id):
        time.sleep(1)
        try:
            resp = self.sendCMD(f"AT+CMQDISCON={mqtt_id}", "Disconnect from MQTT server") 
        except (NbiotCommandError, NbiotCommandTimeout):
            pass
        time.sleep(1)


    def wakeup(self):
        print("Wake up NB-IoT")
        # flush the uart buffer
        self.flushUart()
        # to wake up we must be asleep
        if self.nbiotEnable.value() == 1: self.gotoSleep()
        # set the enable pin to 1 to wake up the chip
        self.nbiotEnable.value(1)


    def gotoSleep(self):
        print("Setting NB-IoT to sleep")
        # set the enable pin to 0 to wake up the chip
        self.nbiotEnable.value(0)
        time.sleep(1)

    # returns a tuple (status, data[])
    def readUart(self, timeout=30):
        data = []
        while timeout:
            line = self.uart.readline()
            if line:
                line = line.decode().strip()
                data.append(line)
                if line.startswith("OK"):
                    return True, data
                if line.startswith("ERROR"):
                    return False, data
            timeout -= 1    
        
        return None, data    
    
    
    def flushUart(self):
        print("Flushing UART...", end="" )
        status = None
        data = None
        try:
            status, data = self.readUart(timeout=1)
        except:
            pass
        print(f"data: {data}")
                

    def sendCMD(self, cmd, comment=None):
        if comment:
            print(comment + " ... ", end="")

        # check that we are not out fo sync and that this data set is for the command issued
        self.uart.write((cmd+'\r\n').encode())
        while True:
            status, data = self.readUart()
            if status == None: break  # Timeout
          
            result = self.parseFor(cmd, data)
            if not result == None:
                break
        
        if comment:
            if status == True:
                print(f"{cmd}: OK: {data}")
            elif status == False:
                print(f"{cmd}: ERROR: {data}")
            else:
                print(f"{cmd}: TIMEOUT: {data}")
                    
        if status == True:
            return data
        elif status == False:
            raise NbiotCommandError(f"nbiot command error: {cmd}", data)
        else:                
            raise NbiotCommandTimeout(f"nbiot command timeout: {cmd}", data)


    def waitFor(self, prefix):
        print(f"Wait until chip responds with {prefix}")
        while True:
            status, data = self.readUart(timeout=1)
            print(f"WaitFor: status: {status}, data: {data}")
            if data:
                for line in data:
                    if line.startswith(prefix):
                        offset = len(prefix)
                        return line[offset:].strip()
            

    def waitForAT(self):
        print("Wait until chip responds to AT commands")
        while True:
            try:
                resp = self.sendCMD("AT")
                print(f"WaitForAT: resp: {resp}")
                return
            
            except (NbiotCommandError, NbiotCommandTimeout) as e:
                pass
            

    def parseFor(self, prefix, resp):
        print(f"parseFor {prefix} in {resp}")
        if resp == None: return None
        for line in resp:
            if line.startswith(prefix):
                offset = len(prefix)
                return line[offset:].strip()


    # report the current RSSI
    def rssi(self):
        try:
            resp = self.sendCMD("AT+CSQ", comment="Get RSSI")
        except (NbiotCommandError, NbiotCommandTimeout) as e:
            return False
        
        result = self.parseFor('+CSQ:', resp)
        if not result:
            print("Unable to get rssi ...")
            return None
               
        ss = result.split(",")[0]
        if ss:            
            if ss == "99":
                print("Error: No Signal")
                return None

            if ss == "0":
                print("Warning: Signal week -113dBm or less")
            else:
                try:
                    rssi = (int(ss) * 2) - 113
                    print(f"rssi: {rssi} dBm")
                    return rssi
                except:
                    return None

    def firmware_version(self):
        resp = self.sendCMD("AT+CGMR", "Get firmware revision")            
        return resp[1]


        


if __name__ == "__main__":
    print("##### Tests #####")
    nbiot = NB_IoT()
    nbiot.wakeup()
    nbiot.waitForAT()
    nbiot.gotoSleep()

    time.sleep(1)
    
    print("##### Factory Reset #####")    
    if not nbiot.factory_reset():
        sys.exit(-1)
    
    time.sleep(1)
    
    print("##### Enable #####")    
    if not nbiot.enable():
        nbiot.disable()
        sys.exit(-2)

    time.sleep(1)
    
#     print("##### Firmware Update #####")    
#     if not nbiot.updateFirmware():
#         nbiot.disable()
#         sys.exit(-2)

    print("##### Check Settings #####")    
    if not nbiot.checkSettings():
        nbiot.disable()
        sys.exit(-3)
    
    time.sleep(1)
    
    print("##### Send Data #####")
    data = {
        "t": 25,
        "p": 50
        }
    if not nbiot.sendMQTT("environment", data ):
        nbiot.disable()
        sys.exit(-4)
    
    print("##### Disable #####")    
    nbiot.disable()
    sys.exit(0)

#     print("##### Wait 5 Secs #####")    
#     time.sleep(5)
# 
#     nbiot.wakeup()
#     nbiot.waitForAT()
# 
# #    nbiot.enable()
#     print("##### Check Settings #####")    
#     nbiot.checkSettings()
# 
#     print("##### Enable #####")    
#     nbiot.enable()
# 
#     print("##### Disable #####")    
#     nbiot.disable()

        
