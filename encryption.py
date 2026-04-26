# =============================================================================
# backend/encryption.py -- Fernet encryption for broker credentials
# =============================================================================

import os
import base64
from cryptography.fernet import Fernet

# Key stored in env or auto-generated and saved
_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secret.key")


def _load_or_create_key() -> bytes:
    key_env = os.getenv("FERNET_KEY")
    if key_env:
        return key_env.encode()
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(_KEY_FILE, "wb") as f:
        f.write(key)
    return key


_fernet = Fernet(_load_or_create_key())


def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
