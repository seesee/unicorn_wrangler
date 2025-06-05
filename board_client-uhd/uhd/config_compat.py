"""
Config compatibility layer for Pi
"""

import json
import os

class ConfigPi:
    """Pi-compatible config class that matches the MicroPython interface"""
    
    def __init__(self, config_file="config.json"):
        # Default configuration
        self.config = {
            "mqtt": {
                "enable": True,
                "broker_ip": "192.168.3.196",
                "broker_port": 1883,
                "client_id": "unicorn_pi",
                "topic_on_off": "unicorn/control/onoff",
                "topic_cmd": "unicorn/control/cmd", 
                "topic_text_message": "unicorn/message/text",
                "topic_publish_status": "unicorn/status"
            },
            "general": {
                "max_runtime_s": 30,
                "brightness": 0.5,
                "debug": False,
                "sequence": ["*"],  # Run random animations
                "ntp_enable": True,
                "ntp_host": "pool.ntp.org",
                "ntp_periodic_update_hours": 12,
                "timezone_offset": 0
            },
            "display": {
                "model": "unicornhathd",
                "status_pixel_x": 15,
                "status_pixel_y": 0
            },
            "text_scroller": {
                "default_repeat_count": 1
            },
            "wifi": {
                "enable": True,  # Assume Pi has network
                "ssid": "",
                "password": ""
            },
            "streaming": {
                "enable": False,  # Streaming not typically used on Pi
                "host": "127.0.0.1",
                "port": 8766,
                "timeout_s": 10,
                "resume_threshold": 0.75
            }
        }
        
        # Load config file if it exists
        self._load_config_file(config_file)
    
    def _load_config_file(self, config_file):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    
                # Merge loaded config with defaults
                for section, values in loaded_config.items():
                    if section in self.config and isinstance(values, dict):
                        self.config[section].update(values)
                    else:
                        self.config[section] = values
                        
                print(f"Loaded configuration from {config_file}")
            else:
                print(f"Config file {config_file} not found, using defaults")
                
        except FileNotFoundError:
            print(f"Config file {config_file} not found, using defaults")
        except json.JSONDecodeError as e:
            print(f"Error parsing config file {config_file}: {e}")
            print("Using default configuration")
        except Exception as e:
            print(f"Error loading config: {e}")
            print("Using default configuration")
    
    def get(self, section, key, default=None):
        """Get configuration value (matches MicroPython interface)"""
        return self.config.get(section, {}).get(key, default)
    
    def __getitem__(self, section):
        """Allow dict-style access to sections"""
        return self.config.get(section, {})
    
    def set(self, section, key, value):
        """Set a configuration value"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
    
    def save(self, config_file="config.json"):
        """Save current configuration to file"""
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"Configuration saved to {config_file}")
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False

# Create global config instance
config = ConfigPi()
