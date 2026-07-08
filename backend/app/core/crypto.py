"""Симметричное шифрование секретов, хранимых в БД (Fernet).

Используется для пароля SMTP (`smtp_settings.password_enc`): пароль кладётся в
базу только в зашифрованном виде и НИКОГДА не отдаётся наружу в открытом виде.

Ключ выбирается так:
  - если задан `settings.FERNET_KEY` (валидный base64-urlsafe 32-байтный ключ
    Fernet) — используется он (рекомендовано в проде: ротация JWT_SECRET не
    обесценит зашифрованные секреты);
  - иначе ключ ДЕТЕРМИНИРОВАННО деривируется из `JWT_SECRET`
    (`urlsafe_b64encode(sha256(JWT_SECRET))` → ровно 32 байта → валидный ключ
    Fernet), чтобы шифрование работало «из коробки» без отдельной переменной.

При порче/подмене шифртекста (InvalidToken) — честный ValidationError, а не
молчаливый возврат мусора.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings
from .errors import ValidationError


def _fernet_key() -> bytes:
    """Возвращает bytes-ключ Fernet: явный FERNET_KEY или дериват из JWT_SECRET."""
    if settings.FERNET_KEY:
        return settings.FERNET_KEY.encode()
    # sha256 даёт ровно 32 байта → urlsafe_b64encode → валидный ключ Fernet.
    digest = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    try:
        return Fernet(_fernet_key())
    except Exception as e:  # неверный формат FERNET_KEY
        raise ValidationError(f"FERNET_KEY некорректен: {e}")


def encrypt_text(plain: str) -> str:
    """Шифрует строку → base64-токен Fernet (str). Пустая строка тоже шифруется."""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_text(token: str) -> str:
    """Расшифровывает токен Fernet. При порче/чужом ключе → ValidationError."""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValidationError(
            "Не удалось расшифровать секрет — неверный FERNET_KEY или данные повреждены"
        )
