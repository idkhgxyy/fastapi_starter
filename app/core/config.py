from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    全局项目配置类
    使用 pydantic-settings 自动从 .env 文件和系统环境变量中读取配置。
    """

    # 项目基础信息
    PROJECT_NAME: str = "FastAPI Starter"
    VERSION: str = "0.1.0"
    TESTING: bool = False

    # 数据库配置
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/fastapi_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS 跨域配置
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000"

    # 日志配置
    LOG_FORMAT: str = "text"  # text | json

    # JWT 鉴权配置
    SECRET_KEY: str = "replace_with_a_long_random_secret_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # LLM 配置 (默认提供 DeepSeek 的占位符，可通过 .env 覆盖)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL_NAME: str = "deepseek-chat"
    LLM_PROVIDER: str = "deepseek"
    LLM_INPUT_PRICE_PER_1K_TOKENS: float = 0.0
    LLM_OUTPUT_PRICE_PER_1K_TOKENS: float = 0.0

    # Mock 模式 — 开启后 LLM 调用返回预设回复，无需 API Key
    LLM_MOCK: bool = False

    # Embedding 配置（独立于 LLM，默认指向本地 Ollama）
    EMBEDDING_BASE_URL: str = "http://localhost:11434/v1"
    EMBEDDING_API_KEY: str = "ollama"
    EMBEDDING_MODEL_NAME: str = "bge-m3"

    # Ollama 服务地址（用于健康检查等）
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    # RAG 配置
    EMBEDDING_DIMENSION: int = 1024

    @model_validator(mode="after")
    def _auto_enable_mock(self) -> "Settings":
        """LLM_API_KEY 为空时自动启用 Mock 模式，实现开箱即用"""
        if not self.LLM_API_KEY and not self.LLM_MOCK:
            import logging

            logging.getLogger(__name__).warning(
                "LLM_API_KEY 未设置，已自动启用 Mock 模式。"
                "设置 LLM_API_KEY 或 LLM_MOCK=false 可关闭。"
            )
            self.LLM_MOCK = True
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # 忽略 .env 中未定义在类里的额外变量
    )


# 实例化一个全局的 settings 对象，供整个项目使用
settings = Settings()
