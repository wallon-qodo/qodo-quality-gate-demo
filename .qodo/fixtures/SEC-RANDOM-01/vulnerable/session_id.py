import random

def session_id() -> int:
    return random.randint(1, 2**32)
