from passlib.context import CryptContext

# 配置 bcrypt 作为密码哈希算法。
# 注意：最新版的 bcrypt (4.0.0+) 去掉了 bcrypt.hashpw 处理长密码的特性，而 passlib 还没更新
# 所以在使用 passlib 时，最好把密码显式转换为最大 72 字节的 bytes。
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    将明文密码进行哈希加密
    """
    # bcrypt 算法的最大支持长度为 72 字节
    if len(password.encode("utf-8")) > 72:
        password = password[:72]
    return pwd_context.hash(password)
