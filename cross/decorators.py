import logging

def Logger(target):
    target.logger = logging.getLogger(target.__name__,)
    return target