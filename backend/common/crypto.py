from cryptography.fernet import Fernet

from common.config import SESSION_ENC_KEY


def _get_fernet() -> Fernet:
    if not SESSION_ENC_KEY:
        raise RuntimeError("SESSION_ENC_KEY not set")
    return Fernet(SESSION_ENC_KEY.encode("utf-8"))


def encrypt_text(value: str) -> str:
    f = _get_fernet()
    token = f.encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(value: str) -> str:
    f = _get_fernet()
    raw = f.decrypt(value.encode("utf-8"))
    return raw.decode("utf-8")
