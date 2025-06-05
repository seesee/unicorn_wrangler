"""
MQTT compatibility layer for Pi
"""

import asyncio
import json
import time
import gc

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

class MQTTServicePi:
    """Pi-compatible MQTT service that matches the MicroPython interface"""
    
    def __init__(self, config, state):
        self.config = config
        self.state = state
        self.client = None
        self.connected = False
        self.client_id = None
        self.connection_attempts = 0
        self.last_connection_attempt = 0
        
        if not MQTT_AVAILABLE:
            print("MQTT not available - install with: pip install paho-mqtt")
            return
            
        # Extract config values
        self.broker = config.get("mqtt", "broker_ip", "127.0.0.1")
        self.port = config.get("mqtt", "broker_port", 1883)
        self.client_id = config.get("mqtt", "client_id", "unicorn_pi")
        
        # Topics
        self.topic_on_off = config.get("mqtt", "topic_on_off", "unicorn/control/onoff")
        self.topic_cmd = config.get("mqtt", "topic_cmd", "unicorn/control/cmd")
        self.topic_text = config.get("mqtt", "topic_text_message", "unicorn/message/text")
        self.topic_status = config.get("mqtt", "topic_publish_status", "unicorn/status")
        
        print(f"MQTT Config: {self.broker}:{self.port} as {self.client_id}")
        self._setup_client()
    
    def _setup_client(self):
        """Setup MQTT client"""
        if not MQTT_AVAILABLE:
            return
        
        try:
            # Try new paho-mqtt API first (v2.0+)
            self.client = mqtt.Client(
                client_id=self.client_id,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION1
            )
        except TypeError:
            try:
                # Fall back to older paho-mqtt API (v1.x)
                self.client = mqtt.Client(self.client_id)
            except Exception as e:
                print(f"Failed to create MQTT client: {e}")
                return
        except Exception as e:
            print(f"Failed to create MQTT client: {e}")
            return
            
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # Enable logging for debugging
        # self.client.enable_logger()  # Uncomment for detailed MQTT debugging
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection"""
        if rc == 0:
            self.connected = True
            self.connection_attempts = 0
            print(f"✓ Connected to MQTT broker at {self.broker}:{self.port}")
            
            # Subscribe to topics
            try:
                client.subscribe(self.topic_on_off)
                client.subscribe(self.topic_cmd)
                client.subscribe(self.topic_text)
                print(f"✓ Subscribed to: {self.topic_on_off}, {self.topic_cmd}, {self.topic_text}")
            except Exception as e:
                print(f"Failed to subscribe: {e}")
        else:
            print(f"✗ MQTT connection failed with code {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection"""
        self.connected = False
        if rc != 0:
            print(f"✗ MQTT unexpected disconnection (code: {rc})")
        else:
            print("MQTT disconnected gracefully")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        topic = msg.topic
        message = msg.payload.decode()
        print(f"MQTT Rx: {topic} = {message}")
        
        # Handle control messages (same logic as MicroPython version)
        if topic == self.topic_on_off:
            if message == "ON":
                self.state.display_on = True
                self.state.interrupt_event.set()
            elif message == "OFFAIR":
                self.state.display_on = True
                self.state.next_animation = None
                self.state.interrupt_event.set()
            elif message == "ONAIR":
                self.state.display_on = True
                self.state.next_animation = "onair"
                self.state.interrupt_event.set()
            elif message == "OFF":
                self.state.display_on = False
                self.state.interrupt_event.set()
                
        elif topic == self.topic_cmd:
            if message == "NEXT":
                self.state.next_animation = None
                self.state.interrupt_event.set()
            elif message == "RESET":
                print("Reset command received - exiting...")
                import sys
                sys.exit(0)
                
        elif topic == self.topic_text:
            if message:
                try:
                    # Try to parse as JSON first
                    if message.startswith('{') and message.endswith('}'):
                        data = json.loads(message)
                        text = data.get("text", "")
                        repeat = int(data.get("repeat", 1))
                    else:
                        text = message
                        repeat = 1
                except Exception:
                    text = message
                    repeat = 1
                    
                self.state.text_message = text
                self.state.text_repeat_count = max(1, repeat)
                self.state.interrupt_event.set()
    
    def publish_status(self, status_dict):
        """Publish status update (matches MicroPython interface)"""
        if not self.connected or not self.client:
            return False
            
        try:
            status_dict["client_id"] = self.client_id
            status_dict["model"] = "stellar"  # Use stellar since we're 16x16
            status_dict["timestamp"] = time.time()
            payload = json.dumps(status_dict)
            result = self.client.publish(self.topic_status, payload)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✓ Published status: {payload}")
                return True
            else:
                print(f"✗ Failed to publish status (rc: {result.rc})")
                return False
        except Exception as e:
            print(f"✗ Failed to publish status: {e}")
            return False
    
    def _should_attempt_connection(self):
        """Check if we should attempt a connection (with backoff)"""
        now = time.time()
        if now - self.last_connection_attempt < 5:  # Wait at least 5 seconds between attempts
            return False
        return True
    
    async def connect(self):
        """Connect to MQTT broker"""
        if not MQTT_AVAILABLE or not self.client:
            return False
        
        if not self._should_attempt_connection():
            return False
            
        try:
            self.last_connection_attempt = time.time()
            self.connection_attempts += 1
            
            print(f"Attempting MQTT connection to {self.broker}:{self.port} (attempt {self.connection_attempts})")
            
            # Connect with timeout
            result = self.client.connect(self.broker, self.port, 60)
            if result == mqtt.MQTT_ERR_SUCCESS:
                # Start the network loop in a separate thread
                self.client.loop_start()
                return True
            else:
                print(f"✗ MQTT connect failed with result: {result}")
                return False
                
        except Exception as e:
            print(f"✗ MQTT connection error: {e}")
            return False
    
    async def loop(self):
        """Main MQTT loop (async compatible)"""
        if not MQTT_AVAILABLE:
            print("MQTT not available")
            return
            
        # Initial connection attempt
        await self.connect()
        
        loop_counter = 0
        while True:
            loop_counter += 1
            
            # Only attempt reconnection if we're not connected and enough time has passed
            if not self.connected and self._should_attempt_connection():
                print("MQTT disconnected, attempting reconnection...")
                await self.connect()
            
            # Periodic cleanup every 120 seconds (2 minutes)
            if loop_counter % 120 == 0:
                gc.collect()
                if loop_counter % 600 == 0:  # Every 10 minutes, more verbose
                    print(f"MQTT loop cleanup (iteration {loop_counter})")
            
            # The MQTT client runs its own loop in a thread, so we just need to sleep
            await asyncio.sleep(1)  # Check every second
