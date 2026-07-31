import marshal

def parse(b: bytes):
    return marshal.loads(b)
