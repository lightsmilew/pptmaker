"""LLM Configuration module - supports OpenAI and Anthropic."""

import os
from pathlib import Path
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from functools import lru_cache

# Always load the project env file independently of the process working directory.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass


class OpenAIConfig(BaseModel):
    """OpenAI API configuration."""
    api_key: str = Field(default="", description="OpenAI API key")
    base_url: str = Field(default="https://api.openai.com/v1", description="API base URL")
    model_name: str = Field(default="gpt-4o-mini", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=327680, ge=1)  # 320KB — safe upper limit for most OpenAI-compatible models

    def is_configured(self) -> bool:
        """Check if the configuration is valid."""
        return bool(self.api_key)


class AnthropicConfig(BaseModel):
    """Anthropic API configuration."""
    api_key: str = Field(default="", description="Anthropic API key")
    base_url: str = Field(default="https://api.anthropic.com/v1", description="API base URL")
    model_name: str = Field(default="claude-3-5-haiku-20241022", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=327680, ge=1)  # 320KB — safe upper limit for most OpenAI-compatible models

    def is_configured(self) -> bool:
        """Check if the configuration is valid."""
        return bool(self.api_key)


class LLMConfig(BaseModel):
    """LLM Configuration with provider selection."""
    provider: Literal["openai", "anthropic"] = Field(default="openai", description="LLM provider")
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)

    @classmethod
    def _parse_int_env(cls, key: str, default: int) -> int:
        """Parse integer from environment variable, supporting expressions like '1024*1024'."""
        import os
        val = os.getenv(key, "")
        if not val:
            return default
        try:
            # Try direct int conversion first
            return int(val)
        except ValueError:
            try:
                # Evaluate math expressions like "1024*1024"
                import ast
                return int(ast.literal_eval(val))
            except Exception:
                return default

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create config from environment variables."""
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai").lower(),
            openai=OpenAIConfig(
                api_key=os.getenv("OPENAI_API_KEY", ""),
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=cls._parse_int_env("OPENAI_MAX_TOKENS", 327680),
            ),
            anthropic=AnthropicConfig(
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
                model_name=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022"),
                temperature=float(os.getenv("ANTHROPIC_TEMPERATURE", "0.7")),
                max_tokens=cls._parse_int_env("ANTHROPIC_MAX_TOKENS", 327680),
            ),
        )

    def get_active_config(self) -> OpenAIConfig | AnthropicConfig:
        """Get the active LLM configuration based on provider."""
        if self.provider == "openai":
            return self.openai
        return self.anthropic

    def get_model_name(self) -> str:
        """Get the current model name."""
        return self.get_active_config().model_name

    def is_configured(self) -> bool:
        """Check if the current provider is properly configured."""
        return self.get_active_config().is_configured()


class LLMClient:
    """Unified LLM client that supports both OpenAI and Anthropic."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()
        self._client = None

    @property
    def provider(self) -> str:
        return self.config.provider

    def _get_openai_client(self):
        """Get or create OpenAI client."""
        if self._client is None or self.provider == "openai":
            try:
                from openai import OpenAI
                cfg = self.config.openai
                self._client = OpenAI(
                    api_key=cfg.api_key,
                    base_url=cfg.base_url if cfg.base_url != "https://api.openai.com/v1" else None,
                )
            except ImportError:
                raise ImportError("Please install openai: pip install openai")
        return self._client

    def _get_anthropic_client(self):
        """Get or create Anthropic client."""
        if self._client is None or self.provider == "anthropic":
            try:
                import anthropic
                cfg = self.config.anthropic
                self._client = anthropic.Anthropic(
                    api_key=cfg.api_key,
                    base_url=cfg.base_url if cfg.base_url != "https://api.anthropic.com/v1" else None,
                )
            except ImportError:
                raise ImportError("Please install anthropic: pip install anthropic")
        return self._client

    def chat(self, messages: list, **kwargs) -> str:
        """Send a chat completion request."""
        if self.config.provider == "openai":
            return self._chat_openai(messages, **kwargs)
        return self._chat_anthropic(messages, **kwargs)

    def _chat_openai(self, messages: list, **kwargs) -> str:
        """OpenAI chat completion."""
        client = self._get_openai_client()
        cfg = self.config.openai

        response = client.chat.completions.create(
            model=cfg.model_name,
            messages=messages,
            temperature=kwargs.get("temperature", cfg.temperature),
            max_tokens=kwargs.get("max_tokens", cfg.max_tokens),
        )
        return response.choices[0].message.content

    def _chat_anthropic(self, messages: list, **kwargs) -> str:
        """Anthropic chat completion."""
        client = self._get_anthropic_client()
        cfg = self.config.anthropic

        # Convert messages format for Anthropic
        system = ""
        anthropic_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content", "")
            else:
                anthropic_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        response = client.messages.create(
            model=cfg.model_name,
            system=system,
            messages=anthropic_messages,
            temperature=kwargs.get("temperature", cfg.temperature),
            max_tokens=kwargs.get("max_tokens", cfg.max_tokens),
        )
        return response.content[0].text

    def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        """Generate text from a prompt."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs)


@lru_cache()
def get_llm_config() -> LLMConfig:
    """Get cached LLM configuration from environment."""
    return LLMConfig.from_env()


def get_llm_client() -> LLMClient:
    """Get a new LLM client instance."""
    return LLMClient(get_llm_config())
