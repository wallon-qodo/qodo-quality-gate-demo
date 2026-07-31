import logging
log = logging.getLogger(__name__)

def issue(user, token):
    log.debug("issued token=%s for %s" % (token, user))
