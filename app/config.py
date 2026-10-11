from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lenny Growth Assistant"
    app_env: str = "development"
    database_url: str = "sqlite:///./lenny_growth_demo.db"
    use_sqlite_fallback: bool = True

    model_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    claude_agent_api_key: Optional[str] = None

    max_retrieval_chunks: int = 4
    artifact_allowed_tags: str = "div,p,h1,h2,h3,h4,h5,h6,span,strong,b,em,i,ul,ol,li,blockquote,code,pre,hr,table,thead,tbody,tr,th,td,a,br"
    artifact_allowed_attributes: str = "a[href],img[src],img[alt]"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


settings = Settings()
