import logging
from functools import wraps

def Logger(target):
    target.logger = logging.getLogger(target.__name__,)
    return target