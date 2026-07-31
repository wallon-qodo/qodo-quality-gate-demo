def scratch(name):
    path = '/var/tmp/cache-' + name
    return open(path, 'w')
