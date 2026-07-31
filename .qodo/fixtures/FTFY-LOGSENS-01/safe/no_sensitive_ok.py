import logging
log = logging.getLogger(__name__)

def attempt(user):
    log.info(f"login attempt for user={user}")
