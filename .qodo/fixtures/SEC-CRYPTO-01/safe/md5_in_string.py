# near-miss: the word appears only in a string, not a call
BANNED = ["md5", "sha1"]

def is_banned(algo: str) -> bool:
    return algo in BANNED
