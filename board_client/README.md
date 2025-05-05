Unicorn Wrangler (Client Device)
===============================

This is the client component of **Unicorn Wrangler**: a flexible, feature-rich framework for running animations, streaming, and MQTT-driven control on your Pimoroni Unicorn (Galactic, Cosmic, or Stellar) with a Raspberry Pi Pico W.

-------------------------------------------------
Quick Features
-------------------------------------------------

- Play dozens of configurable, memory-efficient animations
- Stream GIFs, images, or video frames from a local server (optional)
- MQTT integration for remote control and status (optional)
- NTP time sync and clock modes
- Button controls for skipping or toggling display
- Easy to extend: just drop in new animation modules

-------------------------------------------------
Getting Started
-------------------------------------------------

1. **Copy the files** in `board_client/` to your Unicorn (use Thonny, mpremote, etc).
2. **Edit `config.json`** to set your display model, WiFi, and (optionally) MQTT/streaming settings.
3. **Install dependencies**: Pimoroni MicroPython, `uasyncio`, `ujson`, `umqtt.simple`.
4. **(Optional)**: Set up the streaming server (see main README for details).

-------------------------------------------------
Basic Usage
-------------------------------------------------

- Power up your Unicorn. It will connect to WiFi, sync time, connect to MQTT, and start playing animations.
- Use onboard buttons:
  - **A**: Next animation
  - **B**: Toggle display
  - **C**: (Reserved)
- Control via MQTT (topics are configurable in `config.json`):
  - `unicorn/control/onoff`: `ON`, `OFF`, `ONAIR`, `OFFAIR`
  - `unicorn/control/cmd`: `NEXT`, `RESET`
  - `unicorn/message/text`: Send text or JSON for scrolling messages

-------------------------------------------------
Animations
-------------------------------------------------

- Animations are in the `animations/` folder.
- Add your own by dropping in a `.py` file with a `run(graphics, gu, state, interrupt_event)` coroutine.

-------------------------------------------------
Troubleshooting
-------------------------------------------------

- Check WiFi/MQTT credentials in `config.json`
- Use Thonny or serial console for logs
- Enable debug in config for more info

-------------------------------------------------
More Info
-------------------------------------------------

For full documentation, advanced features, and server setup, see the main README or project repository.

MIT License.

🌈🦄
