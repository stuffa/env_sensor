import time
import ubinascii
import sys
import json
import machine

class NbiotCommandError(Exception):
    def __init__(self, message, resp=None):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        # Add the response data
        self.resp = resp
        
class NbiotCommandTimeout(Exception):
    def __init__(self, message, resp=None):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        # Add the response data
        self.resp = resp


class NBIoT:

    # NOTE: Pins re really GPIO numbers, not the physical pin numbers
    nbiotEnablePin = 14  # The pico pin connected to enable on the NB-IoT chip
    nbiotEnable = None   # This is the pin object that holds the PinState

#     nbiotDtrPin = 17
#     nbiotDtr = None
    
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

    # apn = "telstra.internet"
    
    enabled = False
    client_id = None
    cid = None
    mqtt_id = None


    def __init__(self):
        # Timeout is in (ms)
        self.uart = machine.UART(self.uartPort, self.baudRate, bits=8, parity=None, stop=1, timeout=1000)
        self.nbiotEnable = machine.Pin(self.nbiotEnablePin, machine.Pin.OUT)
        self.nbiotEnable.low()

        # self.nbiotDtr = machine.Pin(self.nbiotDtrPin, machine.Pin.OUT)
        # self.nbiotDtr.value(0)
        
        self.client_id = ubinascii.hexlify(machine.unique_id())


    def enable(self):
        print('--- NB-IoT Enable')

        if self.enabled:
            print("ERROR: enable() reentered - calling disable()")
            self.disable()

        self.wakeup()    # enable the chip

        try:
            print("Checking NB-IoT chip access")
            self.wait_for_at()
            self.flush_uart()

            resp = self.send_cmd("AT+CPIN?", "Check Pin")
            data = self.parse_for("+CPIN:", resp)
            state = data.strip()
            print(f'state: {state}')
            if not state == "READY":
                return False

            # Get the signal strength
            print("Get Signal strength...")
            resp = self.send_cmd("AT+CSQ", "Get Signal Strength")
            data = self.parse_for("+CSQ:", resp)
            if data:
                ss, _other = data.split(",")
                print(f"Signal Strength: {ss}")
            else:
                print ("ERROR: no data")
                return False

            # Wait for PDP to be activated 
            print("Wait for PDP activation...")
            retry = 10
            while retry:    
                # AT+CGACT PDP Context Activate or Deactivate
                resp = self.send_cmd("AT+CGACT?", comment="Get the PDP activated state")
                if  resp:                
                    result = self.parse_for("+CGACT:", resp)
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

        except (NbiotCommandError, NbiotCommandTimeout):
            self.cid = None
            return False

        self.enabled = True
        return True


    def disable(self):
        print('--- NB-IoT Disable')
        self.enabled = False
        self.goto_sleep()


    def factory_reset(self):
        print('--- NB-IoT Factory Reset')
        self.wakeup()
        self.wait_for_at()
        self.wait_for("+CPIN:")

        try:            
            resp = self.send_cmd("AT+CPIN?", "Check Pin")
            data = self.parse_for("+CPIN:", resp)
            state = data.strip()
            if not state == "READY":
                return False

            self.send_cmd("AT&F", "Reset NB-IoT NVRAM")

            # there is no OK reply to the command.
            # so, let's just wait till it responds to AT messages
            self.wait_for_at()
            self.flush_uart() # make sure we don't leave and AT responses

#             self.send_cmd('ATE1', "Enable Echo")
            self.send_cmd('AT*MCGDEFCONT="IP"', "Setting PDP Type: IP")  # set the PDP type
        except (NbiotCommandTimeout, NbiotCommandError):
            return False

        try:
            # save the reset config
            self.send_cmd("AT&W", "Save the reset config")
        except NbiotCommandTimeout:
            pass

        except NbiotCommandError:
            return False

        self.disable()
        return True

    def send_mqtt(self, topic, json_message, server="mqtt.at.martin.cc", port=1883, version=4):
        print('--- NB-IoT MQTT Send')

        mqtt_delay = 1
        retry_cnt = 10

        while retry_cnt:
            mqtt_id = None
            retry_cnt -= 1
            try:
                # Create a new connection
                resp = self.send_cmd(f'AT+CMQNEW="{server}",{port},12000,1024', comment="Create an MQTT client")
                result = self.parse_for("+CMQNEW:", resp)
                if result:
                    mqtt_id = self.parse_for("+CMQNEW:", resp)
                    print (f"mqtt_id: {mqtt_id}")
                else:
                    self.disconnect_mqtt(mqtt_id)
                    continue

                time.sleep(mqtt_delay)

                # Open a connection to the server
                # This may not connect - ie: timeout
                command = f'AT+CMQCON={mqtt_id},{version},"{self.client_id}",{self.keepalive_interval},{self.clean_session},{self.will_flag},"{self.user}","{self.password}"'
                self.send_cmd(command, comment="Connect to the MQTT server")
                # Timeout and Error will raise and exceptions
                # if we get here we got an OK    

                time.sleep(mqtt_delay)

                # add extra data to the payload
                json_message['rssi'] = self.rssi()
                payload = json.dumps(json_message).encode().hex()
                length = len(payload)

                # send the message to the mqtt server
                command = f'AT+CMQPUB={mqtt_id},"{topic}",{self.qos},{self.retained},{self.dup},{length},"{payload}"'
                self.send_cmd(command, comment="Send MQTT message")
                # Timout and Error will both generate exceptions
                # if we get here we have received OK

                # TODO - subscribe and wait for the message to be sent back

                self.disconnect_mqtt(mqtt_id)
                return True

            except (NbiotCommandError, NbiotCommandTimeout):
                self.disconnect_mqtt(mqtt_id)
                continue                

        # Exit due to many retries
        return False
    
    
    def send_http(self, path, json_message, server="mqtt.at.martin.cc", port=80):
        print('--- NB-IoT HTTP Send')
        try:
            resp = self.send_cmd(f'AT+CHTTPCREATE="http://{server}:{port}/"', "New HTTP instance")
            http_id = self.parse_for('+CHTTPCREAT:', resp)
            if not http_id:
                print ("No http_id")
                return False 
            print(f'http_id: {http_id}')
                
            self.send_cmd(f'AT+CHTTPCON={http_id}', "Connect to HTTP server")
            
            time.sleep(3)
            
            header = None
            content_type = "application/json"
            payload = json.dumps(json_message).encode().hex()
            
            self.send_cmd(f'AT+CHTTPSEND={http_id},2,"{path}",{header},"{content_type}",{payload}', "Send POST request")

        except (NbiotCommandError, NbiotCommandTimeout):
            return False
        
        return True
    
    def check_settings(self):
        print('--- NB-IoT Check Settings')
        try:                
            self.send_cmd('AT+CGMR',       "Get Firmware Version")
            self.send_cmd('AT+CPIN?',      "Check if pin required")
            self.send_cmd('AT+CSQ',        "Received Signal Strength")
            self.send_cmd('AT+CEREG?',     "Network Status")
            self.send_cmd('AT+CGACT?',     "Get the cid")
            self.send_cmd('AT+COPS?',      "Operator Selector")
            self.send_cmd('AT+CGCONTRDP=', "Get the IP addresses assigned")
            self.send_cmd('AT+CREVHEX?',   "Data Mode 0:Raw 1:Binary")
            self.send_cmd('AT+CFUN?',      "Radio Functionality 0:Off 1:Full")
            self.send_cmd('AT+CGATT?',     "Network attachment")
            self.send_cmd('AT+CGDCONT?',   "PDP context")
            self.send_cmd('AT+CEREG?',     "Network Status")
            self.send_cmd('AT+CMQNEW?',    "Get the MQTT clients")
            self.send_cmd('AT+CMQCON?',    "Get the MQTT connections")

        except (NbiotCommandError, NbiotCommandTimeout):
            return False
        
        return True
    
    def update_firmware(self):
        print('--- NB-IoT Firmware Update')
        try:
            resp = self.send_cmd("AT+CGMR")
            print(f"Current firmware: {resp[1]}")
            self.send_cmd("AT+CFOTA=1", "Start Firmware update")

        except (NbiotCommandError, NbiotCommandTimeout):
            return False
        
        while True:
            stats, data = self.read_uart()
            print(data)
            result = self.parse_for("+CFOTA:", data)
            if result == "No update package":
                print("Error: No update package")
                return False
            if result == "Update successfully":
                print("Success")
                break
            
        try:
            self.send_cmd("AT+CFOTA=4", "Save Update")
            print(f"Current firmware: {resp[1]}")
            self.send_cmd("AT+CFOTA=1", "Start Firmware update")
        except (NbiotCommandError, NbiotCommandTimeout):
            return False


    def get_http(self, host, path):
        print('--- NB-IoT Get HTTP')
        content = None
        try:
            resp = self.send_cmd(f'AT+CHTTPCREATE="{host}"', f"HTTP create {host}")
            http_id = self.parse_for("+CHTTPCREATE:", resp)
            if not http_id: return False
            
            self.send_cmd(f'AT+CHTTPCON={http_id}', "HTTP connect")
            self.send_cmd(f'AT+CHTTPSEND={http_id},0,"{path}"', f"HTTP Get {path}")
            client_id, code, length, *rubbish = self.wait_for("+CHTTPNMIH:").split(',')
            if client_id == http_id and code == "200":
                client_id, flag, t_len, c_len, content_hex = self.wait_for("+CHTTPNMIC:").split(',')
                content = bytes.fromhex(content_hex).decode('utf-8')     
            self.send_cmd(f'AT+CHTTPDISCON={http_id}', "Disconnect the HTTP socket")
            self.send_cmd(f'AT+CHTTPDESTROY={http_id}', "Destroy the host config")
            
        except (NbiotCommandError, NbiotCommandTimeout):
            return None
        
        return content
    
    
##################################################################

    def disconnect_mqtt(self, mqtt_id):
        time.sleep(1)
        try:
            self.send_cmd(f"AT+CMQDISCON={mqtt_id}", "Disconnect from MQTT server")
        except (NbiotCommandError, NbiotCommandTimeout):
            pass
        time.sleep(1)


    def awake(self):
        return self.nbiotEnable.value() == 1
    
    
    def wakeup(self):
        print("Wake up NB-IoT")
        if self.awake():
            print("NB-IoT is already awake - put it to sleep first")
            self.goto_sleep()

        # wake up the chip
        self.nbiotEnable.high()

#         resp = self.wait_for("+CPIN:")
#         if resp == "READY":
#             self.flush_uart()
#             return True
#         
#         return False
        self.wait_for("+CPIN:")


    def asleep(self):
        return not self.awake()


    def goto_sleep(self):
        print("Setting NB-IoT to sleep")
        # set the enable pin to 0 to wake up the chip
        self.nbiotEnable.low()


    # Returns a tuple (status, data[])
    # May need to read multiple lines
    # Exits on OK or Error or Timeout
    def read_uart(self):
        data = []
        while True:
            line = self.uart.readline()
            if line:
                line = line.decode().strip()
                data.append(line)
            
                if line.startswith("OK"):
                    return True, data    
                if line.startswith("ERROR"):
                    return False, data
            else:
                # Line is None or empty Timout reading readline
                return None, data
    
    # reads UART untill timeout
    def flush_uart(self):
        print("Flushing UART...", end="" )
        while True: # keep flushing untill status = None (timoeout)
            status, data = self.read_uart()
            print(f"Flushed data: {data}")
            if status == None:
                return
                

    def send_cmd(self, cmd, comment=None):
        if comment:
            print(comment + " ... ", end="")

        self.uart.write((cmd+'\r\n').encode())
        status, data = self.read_uart()

        if comment:
            if status == True:
                print(f"OK: {data}")
                return data

            elif status == False:
                print(f"ERROR: {data}")
                raise NbiotCommandError(f"nbiot command error: {cmd}", data)
            else:
                print(f"TIMEOUT: {data}")
                raise NbiotCommandTimeout(f"nbiot command timeout: {cmd}", data)


    # Waits for an unsolicited message
    # returns the value to the right of the prefix: (stripped)  
    def wait_for(self, prefix, attempts=30):
        print(f"Wait until chip responds with {prefix}")
        while attempts:
            status, data = self.read_uart()
            print(f"WaitFor: status: {status}, data: {data}")
            if data:
                for line in data:
                    if line.startswith(prefix):
                        print(f"Found: {prefix}")
                        offset = len(prefix)
                        return line[offset:].strip()
            attempts -=1        
        return None


    # This will loop waiting for AT command to respond
    def wait_for_at(self, attempts=30):
        print("Wait until chip responds to AT commands")
        while attempts:
            try:
                self.send_cmd("AT", "Attention")
                break
            
            except (NbiotCommandError, NbiotCommandTimeout):
                pass
            
            attempts -= 1
        
        self.flush_uart()

        if attempts:
            return True

        return False

    def parse_for(self, prefix, resp):
        print(f"parseFor {prefix} in {resp}")
        if resp == None:
            return None

        for line in resp:
            if line.startswith(prefix):
                offset = len(prefix)
                return line[offset:].strip()

        return None

    # report the current RSSI
    def rssi(self):
        try:
            resp = self.send_cmd("AT+CSQ", comment="Get RSSI")
        except (NbiotCommandError, NbiotCommandTimeout):
            return False
        
        result = self.parse_for('+CSQ:', resp)
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

        return None

    def firmware_version(self):
        resp = self.send_cmd("AT+CGMR", "Get firmware revision")
        return resp[1] # already striped


        
#### Tests ############################

if __name__ == "__main__":
    print("##### Tests #####")
    nbiot = NBIoT()
    print("Wait 5 secs to allow the chip to stablise")
    time.sleep(5)
    
    print("##### Wake Up #####")
    nbiot.wakeup()
    nbiot.wait_for_at()
    nbiot.goto_sleep()

    print("sleeping 5sec to ensure that the chip is fully asleep")
    time.sleep(5)
    
    print("##### Factory Reset #####")    
    if not nbiot.factory_reset():
        sys.exit(-1)
    
    time.sleep(1)    
    
    print("##### Enable #####")    
    if not nbiot.enable():
        nbiot.disable()
        sys.exit(-2)
    
#     print("##### Firmware Update #####")    
#     if not nbiot.update_firmware():
#         nbiot.disable()
#         sys.exit(-2)

    print("##### Check Settings #####")    
    if not nbiot.check_settings():
        nbiot.disable()
        sys.exit(-3)
    
    time.sleep(1)
    
    print("##### Send Data #####")
    json_data = {
        "t": 25,
        "p": 50
        }
    if not nbiot.send_mqtt("environment", json_data):
        nbiot.disable()
        sys.exit(-4)
    
    print("##### Disable #####")    
    nbiot.disable()
    sys.exit(0)

