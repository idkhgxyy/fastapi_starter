import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import settings

def get_fernet_key(secret: str) -> bytes:
    """
    将项目配置的 SECRET_KEY (任意长度) 通过 SHA-256 映射为 Fernet 需要的 32 字节 base64 url-safe 格式的 key。
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)

fernet = Fernet(get_fernet_key(settings.SECRET_KEY))

def encrypt_api_key(api_key: str) -> str:
    """加密 API Key"""
    if not api_key:
        return ""
    return fernet.encrypt(api_key.encode("utf-8")).decode("utf-8")

def decrypt_api_key(encrypted_key: str) -> str:
    """解密 API Key"""
    if not encrypted_key:
        return ""
    try:
        return fernet.decrypt(encrypted_key.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""