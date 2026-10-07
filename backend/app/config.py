"""Application configuration."""

import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

from .llm.config import LLMConfig, get_llm_config


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        # Resolve from the backend package so startup cwd does not affect config.
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        case_sensitive=False,
        extra="ignore",  # Allow extra fields in .env
    )

    # App
    app_name: str = "Folio Studio"
    debug: bool = True

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # LLM Provider - uses LLMConfig for OpenAI and Anthropic
    llm_provider: Literal["openai", "anthropic"] = "openai"

    # Storage
    storage_path: str = "./storage"
    max_file_size: int = 10 * 1024 * 1024  # 10MB

    # PPT Generation
    default_page_count: int = 8
    max_page_count: int = 50
    default_style: str = "商务简约"

    @property
    def llm_config(self) -> LLMConfig:
        """Get LLM configuration."""
        return get_llm_config()

    @property
    def openai_api_key(self) -> str:
        return self.llm_config.openai.api_key

    @property
    def openai_model(self) -> str:
        return self.llm_config.openai.model_name

    @property
    def anthropic_api_key(self) -> str:
        return self.llm_config.anthropic.api_key

    @property
    def anthropic_model(self) -> str:
        return self.llm_config.anthropic.model_name


settings = Settings()
