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
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT 鉴权配置
    SECRET_KEY: str = "replace_with_a_long_random_secret_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # LLM 配置 (切换为本地 Ollama)
    LLM_API_KEY: str = "ollama"
    LLM_BASE_URL: str = "http://ollama:11434/v1"
    LLM_MODEL_NAME: str = "qwen2.5:3b"  # 使用 3B 模型兼顾速度和效果
    EMBEDDING_MODEL_NAME: str = "bge-m3"  # Ollama 上的 bge-m3，维度为 1024
    LLM_PROVIDER: str = "ollama"
    LLM_INPUT_PRICE_PER_1K_TOKENS: float = 0.0
    LLM_OUTPUT_PRICE_PER_1K_TOKENS: float = 0.0

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # 忽略 .env 中未定义在类里的额外变量
    )

# 实例化一个全局的 settings 对象，供整个项目使用
settings = Settings()
