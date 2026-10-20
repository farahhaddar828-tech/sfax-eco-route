"""Central configuration, read from environment variables (12-factor style)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Sfax Eco-Route API"
    environment: str = "dev"
    database_url: str = "sqlite:///./ecoroute.db"

    # Road graph: a GraphML file produced by scripts/import_osm.py.
    # If missing, a small built-in demo graph of central Sfax is used.
    graph_path: str = "data/sfax_drive.graphml"

    # Notifications: every new report is POSTed to the n8n webhook, which emails it.
    n8n_webhook_url: str = ""
    notify_email: str = "farahhaddarrr@gmail.com"
    # Fallback direct SMTP (used only when n8n is not configured)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # AI: provider is one of claude | openai | grok | ollama | none
    llm_provider: str = "ollama"
    llm_model: str = ""          # empty -> provider default
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    xai_api_key: str = ""
    ollama_base_url: str = "http://ollama:11434"

    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
