import json
import time
import machine

class Config:
    
    _config={}
    _version={}
    _name = None
    _config_file = None
    _dirty = False

    
    def __init__(self, config_file="/config.json", version_file="/version.json", name="PicoSensor"):
        self._name = name
        self._config_file = config_file
                    
        try:
            with open(config_file, "rt") as f:
                self._config = json.load(f)
        except:
            self.reset()
        
        try:
            with open(version_file, "rt") as f:
                self._version = json.load(f)
        except:
            self._version = {"version": 0}


    def reset(self):
        self._config = { 'name': self._name, 'sample_count': 4, 'sample_interval': 15, 'tvoc_wait': 3 }
        self._dirty = True
        self.save()


    def save(self):
        if self._dirty:
            with open(self._config_file, "wt") as f:
                json.dump(self._config, f)
        self._dirty = False            


    def get_version(self):
        return self._version['version']
    
    def update(self, data):
        for (k,v) in data.items():
            if k == "utc":
                date, time = v.split("T")
                time, rubbish = time.split("Z")
                yy, mon, dd = date.split("-")
                hh, mm, ss = time.split(":") 
                print(f"date: {date}")
                print(f"time: {time}")
                dt_tuple = (int(yy), int(mon), int(dd), 0, int(hh), int(mm), int(ss), 0,)
                print(f"Tupple: {dt_tuple}")
                machine.RTC().datetime( dt_tuple )
            else:
                self.setVal(k,v)

        self.save()
        
    ############################################    
    
    def getVal(self, key):
        return self._config[key]
    
    def setVal(self, key, value):
        if key in self._config:
            if (self._config[key] == value):
                return
            
        self._config[key] = value
        self._dirty = True
    


if __name__ == "__main__":
    config = Config(name="PicoSensor", config_file="/config_test.json")
    print(config._config)
    config.reset()
    print(config._config)
    print(f"version: {config.get_version()}")
    name = config.getVal('name')
    print(f"name: {name}")
    
    config.setVal('name', 'new name')
    config.save()
    print(f"config: {config._config}")

    sample_interval = config.getVal('sample_interval')
    print(f"sample_interval: {sample_interval}")
    config.update({ "utc": "1959-12-11T22:11:05Z0"})
    print(time.gmtime())
    config.update({ "xxx": "xxx"})
    print(f"_config: {config._config}")
    
