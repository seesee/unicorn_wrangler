from uw.config import config

MODEL = config.get("display", "model", "galactic").lower()

if MODEL == "galactic":
    from galactic import GalacticUnicorn as Unicorn
    from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN as DISPLAY
    WIDTH, HEIGHT = 53, 11
elif MODEL == "cosmic":
    from cosmic import CosmicUnicorn as Unicorn
    from picographics import PicoGraphics, DISPLAY_COSMIC_UNICORN as DISPLAY
    WIDTH, HEIGHT = 32, 32
elif MODEL == "stellar":
    from stellar import StellarUnicorn as Unicorn
    from picographics import PicoGraphics, DISPLAY_STELLAR_UNICORN as DISPLAY
    WIDTH, HEIGHT = 16, 16
else:
    raise RuntimeError(f"Unknown unicorn model: {MODEL}")

gu = Unicorn()
graphics = PicoGraphics(DISPLAY)

def set_brightness(level):
    # set the display brightness (0.0 to 1.0)
    gu.set_brightness(level)
