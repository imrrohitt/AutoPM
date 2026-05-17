from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from core.config import get_settings

_settings = get_settings()
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = _settings.ENCRYPTION_KEY.strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ENCRYPTION_KEY is not configured",
        )
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ENCRYPTION_KEY is invalid",
        ) from e
    return _fernet


def encrypt_value(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt stored secret",
        ) from e
