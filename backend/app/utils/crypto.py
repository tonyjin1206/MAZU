"""加密工具 — Fernet 对称加密，用于存储 API Key / Secret"""

import os
from cryptography.fernet import Fernet

KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".encryption_key")


def _get_or_create_key() -> bytes:
    """获取或生成加密密钥"""
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read().strip()
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    return key


def encrypt(plaintext: str) -> str:
    """加密明文 → base64 密文"""
    if not plaintext:
        return ""
    f = Fernet(_get_or_create_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """解密密文 → 明文"""
    if not ciphertext:
        return ""
    try:
        f = Fernet(_get_or_create_key())
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext  # 兜底：可能未加密的旧数据
