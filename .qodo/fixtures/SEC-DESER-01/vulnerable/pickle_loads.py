import pickle

def run(payload: bytes):
    return pickle.loads(payload)
