# Unicorn Wrangler

Unicorn Wrangler provides a framework that brings a dazzling array (or at least, an array) of functions to your Pimoroni (Galactic, Cosmic, Stellar) Unicorn, powered by an RPi Pico W (1 or 2). 

It provides a relatively easy mechanism to extend and create new animation modules that can be dropped into the main animations directory. (Please feel free to share if you do so, and I'll add them into the main repository).

---

## Features

So, what exactly can it do? Well:

- **Configurable Animation Playback:** Enjoy a configurable gallery of dozens of mostly-attractive animations for your Unicorn. Define a sequence, alternate between fixed and random sequences -- it's up to you.
- **Streaming support:** Stream GIFs, videos or static images using a dedicated docker container service running on your local network over WiFi. The management tool will allow you to upload and manage gifs, jpgs, pngs, mp4s etc and process them to work with your Unicorn.
- **MQTT integration:** Harness your Unicorn with the power of MQTT (or more likely, via Home Assistant), to trigger animation changes, turn the display on or off, put it into "on air" mode, or send scrolling text messages. Your Unicorn can also publish to an MQTT topic so you know what it's up to.
- **NTP synchronisation:** Yes, you can even use your Unicorn as a clock -- and even specify a timezone offset!
- **Modularised control:** Don't need a feature? Just switch it off. Don't like a default? Override it in the config.
- **Button Controls:** Use onboard buttons to skip animations or toggle the display. TBH I did not spend too long on the buttons.
- **Asynchronous event support:** Start a job and have it run every so often (e.g. switching debug on will provide various stats every x seconds. NTP will resync every 12 hours, etc).

---

## Getting Started

### 1. Hardware Requirements

- Pimoroni Galactic Unicorn (53x11), Cosmic Unicorn (32x32), or Stellar Unicorn (16x16)
- (Optional) WiFi network
- (Optional) MQTT broker
- (Optional) Somewhere you can run a local docker container (for streaming and basic transcoding).

A simulator for running on a desktop host is also provided (tested on Linux and MacOS, YMMV on Windows but it should probably work).

### 2. Software Requirements

- Pimoroni MicroPython (latest stable version for your Unicorn device recommended)
- `uasyncio`, `ujson`, `umqtt.simple` external libraries

### 3. Installation

1. Clone or Download this repository to your computer.
2. Copy the files and directories in `board_client` to your Unicorn using Thonny, mpremote, or whatever else works for you.
3. Install dependencies (see above) if not already present on your device.
4. Edit `config.json` to set your Unicorn type, WiFi credentials, MQTT broker, and other preferences.

   Example:
   ```json
   {
     "display": {
       "model": "galactic"
     },
     "wifi": {
       "enable": true,
       "ssid": "YOUR_WIFI_SSID",
       "password": "YOUR_WIFI_PASSWORD"
     },
     "mqtt": {
       "enable": true,
       "broker_ip": "192.168.x.x",
       "broker_port": 1883,
       "client_id": "galactic_unicorn_1"
     }
     ...
   }

5. (Optional) Set up a streaming server if you want to stream videos, animated gifs, static images or (my personal favourite) a QR-Code clock.

## Usage

- Power up your Unicorn with the `client_device` code and config in place.
- The system will:
  - Connect to WiFi (if enabled)
  - Sync time via NTP (if enabled)
  - Connect to MQTT (if enabled)
  - Start playing animations in a random or configured sequence. By default it will alternate between the streaming server (if set up) and a random animation.

### Controls

- **Button A:** Skip to the next animation
- **Button B:** Toggle display on/off
- **Button C:** (TBD)

### MQTT Topics

All topics are configurable via the config, but by default they are:

- `unicorn/control/onoff`: Send `ON` or `OFF` to turn the display on or off. Use `ONAIR` and `OFFAIR` to toggle "On Air" mode (useful for meetings)
- `unicorn/control/cmd`: Send `NEXT` to skip animation, `RESET` to reboot
- `unicorn/message/text`: Send a string or JSON (`{"text": "Hello!", "repeat": 2}`) to display scrolling text the specified number of times.

### Streaming

- If enabled, the system will connect to the configured streaming server and display streamed frames at up to 15 FPS.  
  **Note:** The performance does change depending on your Unicorn model. Generally 15 fps is achievable on all but the Cosmic Unicorn with the Pico W v1, which tops out around 8-9 FPS. The Cosmic Unicorn with Pico W 2 can get up to 25 fps but generally it's highly uneven so better to limit it to something more consistently achievable.
- See "server" section for instructions on how to set up and use. You don't have to use Docker, you can just install the dependencies and run it on pretty-much any linux host (YMMV with other platforms), but it's definitely the most convenient option.

---

## Animations

Animations are stored in the `animations/` directory and are lazily loaded with active cleanup when completed. This means you can add animations that make the most of the available memory.

You can add your own animations by dropping a new `.py` file with a `run(graphics, gu, state, interrupt_event)` coroutine into the `animations/` directory and restarting. It'll automatically get picked up (or you can specify it to run in a loop, or with other animations, via the `config.json`).

Some included animations:
- Jellyfish Aquarium
- Fireflies
- Duelling Snakes
- Maze Generator
- Sparkles
- Failsafe
- ...and dozens more (but they aren't all winners)

---

## Configuration

All settings are in `config.json`.  
You can control:

- WiFi and MQTT settings
- Streaming server details
- Animation sequence and timing
- Display model and brightness
- Debug mode

---

## Contributing and Notes

Pull requests, new animations, and improvements are welcome. There will be bugs. I've tested on the Galactic Unicorn (P1), and Cosmic Unicorn (P1 and P2 versions), but not the Stellar Unicorn. I have however tested on the Unicorn HD running on a Raspberry Pi 3A in UHD mode, and can confirm it works quite well there too. All core functionality will work just fine (just as it will on any Pico W with the Pimoroni micropython installed), but some animations might not render properly. 

Please keep in mind the constraints of MicroPython and the Pico W. 

All animations run stably on both V1 and V2 of the Pico W Unicorns, however the Pico W V2 does run some things a little smoother due to its (moderately) increased power. Please also keep these constraints in mind. An earlier version was able to run for ~17 minutes before crashing and restarting. I recommend setting a maximum of 20 iterations (set in config.json -> general -> max_iterations: 20) for Pico 1 devices (this will restart the device automatically after 20 animations have been played, you can increase or decrease this depending on which animations you're using or whether you are using streaming. The limited memory on the Pico 1 units means that even clearing the memory as we do leads to situations where it is impossible to allocate enough contiguous memory which leads to an eventual crash that might not be recoverable. I've tried to find better solutions but options in micropython for memory management are quite limited. Better solutions will be gratefully welcomed).

---

## License

MIT License (see LICENSE file).

---

## Credits

- Pimoroni for the Unicorn hardware and MicroPython drivers
- MicroPython community
- All contributors and testers
- t3.chat for access to various LLM models that were quite useful when they weren't hallucinating or spouting total b\*ll\*cks.

---

## Troubleshooting

- **WiFi not connecting?** Double-check your SSID and password in `config.json`.
- **MQTT not working?** Ensure your broker is reachable and topics are correct.
- **Animations not running?** Check for typos in animation filenames or syntax errors in the device logs. (Use the simulator or check what is output to serial).
- **Experiencing lockups or streaming issues?** I've found moving the Unicorn a few inches to the left or right can mean the difference between smooth solid playback and the jankiest, most unwatchable mess. Also note: The MQTT library used is not asynchronous. This usually doesn't matter, but it will lock up the Unicorn for several seconds if it ever needs to reconnect to the broker due to network instability etc. If you aren't using MQTT, disable it.

Using Thonny, mpremote or minicom will provide access to reasonably good logs to help identify and address issues. Additional debug logging can be enabled in the config.

---

🌈🦄

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/seesee/unicorn_wrangler)
