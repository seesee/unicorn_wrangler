import uasyncio
import machine
import uerrno

from uw.state import state
from uw.logger import log
from uw.config import config

try:
    from umqtt.simple import MQTTClient
except ImportError:
    MQTTClient = None

class MQTTService:
    def __init__(self, status_callback=None):
        self.client = None
        self.client_id = None
        self.connected = False
        self.connection_attempted = False
        self.disable_reconnect = False
        self.status_callback = status_callback  # Callback to update service status

    def connect(self):
        if not MQTTClient:
            log("MQTTClient not available (umqtt.simple not installed)", "WARN")
            return False

        # Mark that we've attempted connection
        self.connection_attempted = True
        
        broker = config.get("mqtt", "broker_ip", "127.0.0.1")
        port = config.get("mqtt", "broker_port", 1883)
        client_id = config.get("mqtt", "client_id", "unicorn")

        try:
            self.client = MQTTClient(client_id, broker, port)
            self.client.set_callback(self._on_message)
            # Note: self.client.connect() is blocking and will stall other tasks if the
            # broker is unavailable. This is a limitation of umqtt.simple.
            self.client.connect()
            self.client.sock.setblocking(False)
            self.connected = True
            self.client_id = client_id
            log(f"Connected to MQTT broker at {broker}:{port}", "INFO")
            
            # Notify service manager that MQTT is connected but pending final confirmation
            if self.status_callback:
                self.status_callback("mqtt", "connected_pending")
            
            # Subscribe to topics as needed
            self.client.subscribe(config.get("mqtt", "topic_on_off", "unicorn/control/onoff"))
            self.client.subscribe(config.get("mqtt", "topic_cmd", "unicorn/control/cmd"))
            self.client.subscribe(config.get("mqtt", "topic_text_message", "unicorn/message/text"))
            return True
        except Exception as e:
            log(f"MQTT connection failed: {e}", "WARN")
            self.connected = False
            return False

    def publish_status(self, status_dict):
        """Publish a status update as JSON to the status topic."""
        if not self.connected or not self.client:
            return False
        import ujson
        topic = config.get("mqtt", "topic_publish_status", "unicorn/status")
        try:
            status_dict["client_id"] = self.client_id
            payload = ujson.dumps(status_dict)
            self.client.publish(topic, payload)
            log(f"Published status to {topic}: {payload}", "DEBUG")
            return True
        except Exception as e:
            log(f"Failed to publish status: {e} - continuing MQTT listening", "WARN")
            return False

    def _on_message(self, topic, msg):
        topic = topic.decode() if isinstance(topic, bytes) else topic
        msg = msg.decode() if isinstance(msg, bytes) else msg
        log(f"MQTT Rx: {topic} = {msg}", "DEBUG")
        # Handle ON/OFF, NEXT and text message
        if topic == config.get("mqtt", "topic_on_off", "unicorn/control/onoff"):
            if msg == "ON":
                log("Display on from MQTT", "INFO")
                state.display_on = True
                state.interrupt_event.set()
            elif msg == "OFF":
                log("Display off from MQTT", "INFO")
                state.display_on = False
                state.interrupt_event.set()
            elif msg == "ONAIR":
                log("ON AIR from MQTT", "INFO")
                state.display_on = True
                state.next_animation = "onair"
                state.interrupt_event.set()
            elif msg == "OFFAIR":
                log("OFF AIR from MQTT, releasing lock if set", "INFO")
                state.display_on = True
                state.next_animation = None
                state.interrupt_event.set()
        elif topic == config.get("mqtt", "topic_cmd", "unicorn/control/cmd"):
            if msg == "NEXT":
                # release lock if set
                state.next_animation = None
                state.interrupt_event.set()
            elif msg == "RESET":
                machine.reset()

        elif topic == config.get("mqtt", "topic_text_message", "unicorn/message/text"):
            if msg:
                import ujson
                try:
                    if msg.startswith('{') and msg.endswith('}'):
                        data = ujson.loads(msg)
                        text = data.get("text", "")
                        repeat = int(data.get("repeat", 1))
                    else:
                        text = msg
                        repeat = 1
                except Exception:
                    text = msg
                    repeat = 1
                state.text_message = text
                state.text_repeat_count = max(1, repeat)
                state.interrupt_event.set()

    async def loop(self):
        """Message handling loop - only runs after successful connection"""
        while self.connected:
            try:
                self.client.check_msg()
            except OSError as e:
                if e.args[0] == uerrno.EAGAIN:
                    pass # No data available right now, check again later.
                else:
                    # Some other OSError, treat as a connection error.
                    log(f"MQTT connection lost: {e} - not reconnecting (design choice)", "WARN")
                    self.connected = False
                    self.disable_reconnect = True  # Never try to reconnect
                    break
            except Exception as e:
                log(f"MQTT error: {e} - not reconnecting (design choice)", "WARN")
                self.connected = False
                self.disable_reconnect = True  # Never try to reconnect
                break
                    
            await uasyncio.sleep_ms(100)
        
        log("MQTT message loop ended", "INFO")
