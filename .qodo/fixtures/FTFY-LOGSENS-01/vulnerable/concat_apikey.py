import logging
log = logging.getLogger(__name__)

def call(api_key):
    log.warning("using api_key=" + api_key)
