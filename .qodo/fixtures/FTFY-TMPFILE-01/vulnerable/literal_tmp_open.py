import os

def scratch():
    return open('/tmp/myapp_' + str(os.getpid()), 'w')
