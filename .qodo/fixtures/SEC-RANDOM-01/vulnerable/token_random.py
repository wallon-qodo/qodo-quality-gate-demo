import random

def make_token() -> str:
    return "".join(random.choice("abcdef0123456789") for _ in range(32))
