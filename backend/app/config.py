from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Database — SQLite for zero-config local dev
    database_url: str = "sqlite+aiosqlite:///./poltaishow.db"

    # AI / LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = ""

    # Analysis limits (MVP)
    max_files: int = 200
    max_file_size_kb: int = 500
    analysis_ttl_hours: int = 24

    # Storage
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50


settings = Settings()
