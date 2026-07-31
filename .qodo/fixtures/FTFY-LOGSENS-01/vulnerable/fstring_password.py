import logging
log = logging.getLogger(__name__)

def attempt(user, password):
    log.info(f"login user={user} password={password}")
