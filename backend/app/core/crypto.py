"""
Symmetric encryption for user-supplied provider API keys (ProviderCredential
rows). Keys are encrypted at rest with Fernet (AES-128-CBC + HMAC, from the
`cryptography` package) using a server-held master key -- never stored or
logged in plaintext, never returned to the client after save.

The master key is NOT the same as JWT_SECRET -- a compromised JWT secret
(bad, but only lets someone forge sessions) and a compromised credential
key (catastrophic, decrypts every user's provider API keys) are different
blast radii and should rotate independently.
"""
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

settings = get_settings()
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.credential_encryption_key:
            raise RuntimeError(
                "CREDENTIAL_ENCRYPTION_KEY is not set. Generate one with:\n"
                "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
                "and set it in .env -- required before any provider credentials can be saved."
            )
        _fernet = Fernet(settings.credential_encryption_key.encode())
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        # Wrong/rotated master key, or corrupted row -- never leak which,
        # just fail closed. A caller seeing this should treat the
        # credential as unusable and prompt the user to re-enter it.
        raise ValueError("Stored credential could not be decrypted") from exc


def mask_key(plaintext: str) -> str:
    """For display only -- e.g. 'sk-ant-...wXyZ'. Never enough to reconstruct the key."""
    if len(plaintext) <= 8:
        return "•" * len(plaintext)
    return f"{plaintext[:6]}...{plaintext[-4:]}"