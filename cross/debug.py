import sys


def debugger_is_active() -> bool:
     """Return if the debugger is currently active"""
     gettrace = getattr(sys, 'gettrace', lambda : None)
     return gettrace() is not None
