import uasyncio

class State:
    def __init__(self):
        self.animation_active = False
        self.streaming_active = False
        self.display_on = True
        self.interrupt_event = uasyncio.Event()
        self.text_message = None
        self.next_animation = None
        self.text_repeat_count = 1
        self.text_scrolling_active = False
        self.transition_mode = None
        self.wifi_connected = False
        self.mqtt_connected = False
        self.mqtt_service = None

state = State()
