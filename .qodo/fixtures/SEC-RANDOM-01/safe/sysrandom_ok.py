import random

_sr = random.SystemRandom()

def pick(seq):
    return _sr.choice(seq)
