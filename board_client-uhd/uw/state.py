"""
State compatibility - redirects to uhd compatibility layer
"""

# Import from our compatibility layer
from uhd.utils import StatePi

# Create global state instance matching MicroPython interface
state = StatePi()

__all__ = ['state']
