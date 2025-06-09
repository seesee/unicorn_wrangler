#!/usr/bin/env python3

import sim.micropython_compat

import sys
import types

import sim.mqtt_compat
import argparse

# Create a fake module uw.mqtt_service with MQTTService = MQTTServiceSim
mqtt_service_mod = types.ModuleType("uw.mqtt_service")
mqtt_service_mod.MQTTService = sim.mqtt_compat.MQTTServiceSim
sys.modules["uw.mqtt_service"] = mqtt_service_mod

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description="Unicorn Wrangler Desktop Simulator"
)
parser.add_argument(
    "--model",
    choices=["cosmic", "galactic", "stellar"],
    default="cosmic",
    help="Which Unicorn model to simulate (default: cosmic)"
)
args = parser.parse_args()

# Patch sys.path so imports work
import os
sys.path.insert(0, os.path.abspath("."))

# Set environment variable for model selection
os.environ["UNICORN_SIM_MODEL"] = args.model

# Import the simulation hardware layer
from sim.hardware_sim import graphics, gu, set_brightness, WIDTH, HEIGHT, MODEL

# Patch uw.hardware to point to our sim hardware
import uw
sys.modules["uw.hardware"] = sys.modules["sim.hardware_sim"]

# Now import the rest of the framework
from uw.config import config
from uw.logger import setup_logging, log
from uw.state import state
from uw.mqtt_service import MQTTService

from uw.animation_service import run_random_animation, run_named_animation, get_animation_list
from uw.background_tasks import debug_monitor
from uw.transitions import melt_off, countdown

import uasyncio

state.wifi_connected = True

# Minimal state for simulation (no wifi/mqtt/buttons)
async def main():
    setup_logging(config.get("general", "debug", False))
    set_brightness(config.get("general", "brightness", 0.75))
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    gu.update(graphics)

    # Optionally start debug monitor
    if config.get("general", "debug", False):
        uasyncio.create_task(debug_monitor())

    if config.get("mqtt", "enable", False):
        try:
            mqtt_service = MQTTService(config, state)
            state.mqtt_service = mqtt_service
            uasyncio.create_task(mqtt_service.loop())
            log("MQTT service started.", "INFO")
        except Exception as e:
            log(f"Failed to start MQTT service: {e}", "ERROR")
            state.mqtt_service = None
    else:
        log("MQTT disabled.", "INFO")
    sequence = list(config.get("general", "sequence", ["*"]))
    animation_list = get_animation_list()

    while True:
        if not state.display_on:
            await melt_off()
            while not state.display_on:
                await uasyncio.sleep(0.2)
            await countdown()

        job = sequence.pop(0)
        sequence.append(job)

        if job == "*" or job == "animation":
            await run_random_animation(config.get("general", "max_runtime_s", 120))
        elif job in animation_list:
            await run_named_animation(job, config.get("general", "max_runtime_s", 120))
        else:
            log(f"Unknown sequence job: {job}", "WARN")

if __name__ == "__main__":
    try:
        uasyncio.run(main())
    except KeyboardInterrupt:
        print("Simulation stopped by user.")
    except Exception as e:
        log(f"Fatal error: {e}", "ERROR")
        try:
            graphics.set_pen(graphics.create_pen(255, 0, 0))
            graphics.clear()
            gu.update(graphics)
        except Exception:
            pass
