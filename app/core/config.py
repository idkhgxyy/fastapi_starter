from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    全局项目配置类
    使用 pydantic-settings 自动从 .env 文件和系统环境变量中读取配置。
    """
    # 项目基础信息
    PROJECT_NAME: str = "FastAPI Starter"
    VERSION: str = "0.1.0"
    
    # 数据库配置
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/fastapi_db"
    
    # JWT 鉴权配置
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # 忽略 .env 中未定义在类里的额外变量
    )

# 实例化一个全局的 settings 对象，供整个项目使用
settings = Settings()
