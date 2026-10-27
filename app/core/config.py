from typing import Optional

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
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL_NAME: str = "deepseek-flash"
    LLM_PROVIDER: str = "deepseek"
    LLM_INPUT_PRICE_PER_1K_TOKENS: float = 0.0
    LLM_OUTPUT_PRICE_PER_1K_TOKENS: float = 0.0

    # 成本熔断（BYOK 云端模型按量计费，单位：元/CNY）
    # 红线默认 45 元：对应 50 元的节省计划预留 5 元缓冲（出账有 2~10 分钟延迟）。
    # 设为 <=0 可关闭熔断。单价为忙时价（保守估计，闲时实际花费更低）。
    LLM_BUDGET_CNY: float = 45.0
    LLM_INPUT_PRICE_PER_1M: float = 3.0
    LLM_OUTPUT_PRICE_PER_1M: float = 9.0

    # Mock 模式 — 开启后 LLM 调用返回预设回复，无需 API Key
    # None 表示未显式配置；LLM_API_KEY 为空且未显式配置时才自动启用 Mock
    LLM_MOCK: Optional[bool] = None

    # Embedding 配置（独立于 LLM，默认指向本地 Ollama）
    EMBEDDING_BASE_URL: str = "http://localhost:11434/v1"
    EMBEDDING_API_KEY: str = "ollama"
    EMBEDDING_MODEL_NAME: str = "bge-m3"

    # Ollama 服务地址（用于健康检查等）
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    # 云端不可用（调用失败/预算触顶/未配置 Key）时的本地降级模型
    OLLAMA_FALLBACK_MODEL: str = "qwen2.5:3b"
    # 轻量部署（如 2G 内存云服务器）可设为 false：不部署 Ollama，
    # 降级链关闭、embedding 全走云端 API、健康检查不再报告 Ollama
    OLLAMA_ENABLED: bool = True

    # RAG 配置
    EMBEDDING_DIMENSION: int = 1024

    # 语义缓存：相似问题命中缓存则免调用 LLM（省钱 + 降延迟）
    SEMANTIC_CACHE_ENABLED: bool = True
    # 阈值与 embedding 模型强相关，调整前必须跑 evaluation/：
    # 线上 text-embedding-v4 同义改写实测约 0.84–1.00，无关问题多数低于 0.80；
    # ≥0.95 直接命中，0.80–0.95 由短 LLM 校验；专有名词/数字不一致还会额外校验。
    SEMANTIC_CACHE_THRESHOLD: float = 0.95  # 高置信度直接命中
    SEMANTIC_CACHE_CANDIDATE_THRESHOLD: float = 0.80  # 灰区下限，低于此值不校验
    SEMANTIC_CACHE_TOP_CANDIDATES: int = 3  # 最近 N 条逐条过守卫，避免 top1 被拒就整体未命中
    SEMANTIC_CACHE_TTL_DAYS: int = 30  # 条目超过该天数不再命中，写入时顺带清理
    SEMANTIC_CACHE_MAX_ENTRIES_PER_USER: int = 200  # 单用户缓存上限，防止无限增长

    # 闲时批量任务（Celery beat 每天 22:30 北京时间触发，落在百炼闲时窗口）
    SUMMARIZE_MAX_DOCS_PER_RUN: int = 5  # 每轮最多摘要的文档数

    # Agent 任务（目标 → Markdown 成果）：按"固定流水线"生成，控制单任务成本
    AGENT_TASK_MAX_SECTIONS: int = 5  # 大纲最多几节（每节一次 LLM 调用）
    AGENT_TASK_MAX_INPUT_CHARS: int = 8000  # 送入模型的目标+材料总长度上限
    AGENT_TASK_MAX_TOKENS: int = 30000  # 单任务累计 token 上限，超出中止
    AGENT_TASK_SECTION_MAX_TOKENS: int = 2800  # 单节输出上限（偏紧会截断长节）
    SUMMARY_MAX_INPUT_CHARS: int = 4000  # 送入 LLM 的文档内容截断长度

    @model_validator(mode="after")
    def _auto_enable_mock(self) -> "Settings":
        """LLM_API_KEY 为空且未显式配置 LLM_MOCK 时自动启用 Mock 模式，实现开箱即用。

        用户显式设置 LLM_MOCK=false 时必须尊重（例如纯 BYOK 场景：无全局 Key，
        每个用户自带 Key），不能强行覆盖。
        """
        if not self.LLM_API_KEY and self.LLM_MOCK is None:
            import logging

            logging.getLogger(__name__).warning(
                "LLM_API_KEY 未设置且未显式配置 LLM_MOCK，已自动启用 Mock 模式。"
                "设置 LLM_API_KEY 或在配置中显式设置 LLM_MOCK=false 可关闭。"
            )
            self.LLM_MOCK = True
        elif self.LLM_MOCK is None:
            self.LLM_MOCK = False
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # 忽略 .env 中未定义在类里的额外变量
    )


# 实例化一个全局的 settings 对象，供整个项目使用
settings = Settings()
