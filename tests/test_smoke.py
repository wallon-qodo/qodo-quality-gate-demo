from app.crypto_utils import hash_password, verify_password


def test_roundtrip():
    digest, salt = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", digest, salt)
    assert not verify_password("wrong", digest, salt)
