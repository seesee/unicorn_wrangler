"""
Hardware compatibility - redirects to uhd compatibility layer
"""

# Import from our compatibility layer
from uhd.hardware_compat import graphics, gu, WIDTH, HEIGHT, MODEL, set_brightness

# Re-export everything so existing imports work
__all__ = ['graphics', 'gu', 'WIDTH', 'HEIGHT', 'MODEL', 'set_brightness']
