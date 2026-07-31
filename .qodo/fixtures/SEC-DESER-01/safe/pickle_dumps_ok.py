import pickle

def serialise(obj) -> bytes:
    # writing is not the dangerous direction
    return pickle.dumps(obj)
