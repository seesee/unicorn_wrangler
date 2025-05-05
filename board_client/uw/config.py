# config.py
import ujson

_DEFAULT_CONFIG = {
    "wifi": {
        "enable": False,
        "ssid": "",
        "password": ""
    },
    "mqtt": {
        "enable": False,
        "broker_ip": "127.0.0.1",
        "broker_port": 1883,
        "client_id": "unicorn"
    },
    "streaming": {
        "enable": False,
        "host": "127.0.0.1",
        "port": 8766,
        "timeout_s": 10,
        "resume_threshold": 0.75
    },
    "general": {
        "sequence": ["streaming", "*"],
        "timezone_offset": 0,
        "debug": False,
        "max_runtime_s": 10
    },
    "display": {
        "model": "galactic",
        "status_pixel_x": 52,
        "status_pixel_y": 0
    },
    "text_scroller": {
        "default_repeat_count": 1
    }
}

class Config:
    def __init__(self, filename="config.json"):
        self._config = {}
        self._config.update(_DEFAULT_CONFIG)
        try:
            with open(filename, "r") as f:
                loaded = ujson.load(f)
                for section, values in loaded.items():
                    if section in self._config and isinstance(values, dict):
                        self._config[section].update(values)
                    else:
                        self._config[section] = values
        except Exception:
            pass

    def get(self, section, key, default=None):
        return self._config.get(section, {}).get(key, default)

    def __getitem__(self, section):
        return self._config.get(section, {})

config = Config()
