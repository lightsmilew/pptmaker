"""LLM Configuration module - supports OpenAI and Anthropic."""

import os
import hashlib
import json
import threading
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from urllib.parse import urlparse
from .telemetry import record_call
from collections import OrderedDict
from pathlib import Path
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from functools import lru_cache

_response_cache = OrderedDict()
_response_cache_lock = threading.Lock()

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
    max_tokens: int = Field(default=4096, ge=1)

    def is_configured(self) -> bool:
        """Check if the configuration is valid."""
        return bool(self.api_key)


class AnthropicConfig(BaseModel):
    """Anthropic API configuration."""
    api_key: str = Field(default="", description="Anthropic API key")
    base_url: str = Field(default="https://api.anthropic.com/v1", description="API base URL")
    model_name: str = Field(default="claude-3-5-haiku-20241022", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)

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
                max_tokens=cls._parse_int_env("OPENAI_MAX_TOKENS", 4096),
            ),
            anthropic=AnthropicConfig(
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
                model_name=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022"),
                temperature=float(os.getenv("ANTHROPIC_TEMPERATURE", "0.7")),
                max_tokens=cls._parse_int_env("ANTHROPIC_MAX_TOKENS", 4096),
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


@dataclass
class CachedResponse:
    expires_at: float
    text: str


class LLMClient:
    """Unified LLM client that supports both OpenAI and Anthropic."""

    def __init__(self, config: Optional[LLMConfig] = None, role: str = "default"):
        self.config = config or LLMConfig.from_env()
        self.role = role
        self._client = None
        self._client_lock = threading.Lock()
        self._call_usage = threading.local()

    @property
    def provider(self) -> str:
        return self.config.provider

    def _get_openai_client(self):
        with self._client_lock:
            if self._client is None:
                from openai import OpenAI
                cfg = self.config.openai
                self._client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url,
                                      timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
                                      max_retries=1)
        return self._client

    def _get_anthropic_client(self):
        with self._client_lock:
            if self._client is None:
                import anthropic
                cfg = self.config.anthropic
                self._client = anthropic.Anthropic(api_key=cfg.api_key, base_url=cfg.base_url,
                                                 timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
                                                 max_retries=1)
        return self._client

    def chat(self, messages: list, **kwargs) -> str:
        started = time.perf_counter()
        cfg = self.config.get_active_config()
        cache = kwargs.pop("cache", False)
        options = {"temperature": cfg.temperature, "max_tokens": cfg.max_tokens, **kwargs}
        if urlparse(cfg.base_url).hostname == "api.deepseek.com":
            options["reasoning_effort"] = os.getenv("DEEPSEEK_" + self.role.upper() + "_EFFORT",
                                                  os.getenv("DEEPSEEK_REASONING_EFFORT", "none"))
        # Include all effective settings and credentials (hashed only) to isolate providers/accounts.
        payload = json.dumps([self.config.model_dump(), messages, options],
                             ensure_ascii=False, sort_keys=True, default=str)
        cache_key = hashlib.sha256(payload.encode("utf-8")).hexdigest() if cache else None
        cached = None
        if cache_key:
            with _response_cache_lock:
                entry = _response_cache.get(cache_key)
                if entry and entry.expires_at > time.monotonic():
                    _response_cache.move_to_end(cache_key)
                    cached = entry.text
                elif entry:
                    del _response_cache[cache_key]
        if cached is not None:
            record_call(role=self.role, model=cfg.model_name, provider=self.provider,
                        duration_ms=round((time.perf_counter()-started)*1000, 1),
                        response_cache_hit=True, input_tokens=0, output_tokens=0,
                        cached_input_tokens=0, usage_reported=False, success=True)
            return cached
        self._call_usage.value = {}
        success = False
        call_id = uuid.uuid4().hex
        try:
            from ..storage.account_repository import account_repository
            account_repository().reserve_output(call_id, min(options["max_tokens"],cfg.max_tokens))
            result = (self._chat_openai(messages, **options) if self.provider == "openai"
                      else self._chat_anthropic(messages, **options))
            success = True
            # Bounded TTL cache; never store giant image responses or truncated completions.
            if cache_key and result and len(result.encode("utf-8")) <= 65536:
                with _response_cache_lock:
                    _response_cache[cache_key] = CachedResponse(time.monotonic()+600, result)
                    _response_cache.move_to_end(cache_key)
                    while len(_response_cache) > 128:
                        _response_cache.popitem(last=False)
            return result
        finally:
            record_call(role=self.role, model=cfg.model_name, provider=self.provider,
                        call_id=call_id,
                        duration_ms=round((time.perf_counter()-started)*1000, 1),
                        response_cache_hit=False, success=success,
                        **self._call_usage.value)

    def _chat_openai(self, messages: list, **kwargs) -> str:
        cfg = self.config.openai
        request = dict(model=cfg.model_name, messages=messages,
                       temperature=kwargs["temperature"],
                       max_tokens=min(kwargs["max_tokens"], cfg.max_tokens))
        # Third-party OpenAI-compatible gateways must explicitly opt into JSON mode.
        mode = os.getenv("LLM_JSON_MODE", "auto")
        official = urlparse(cfg.base_url).hostname == "api.openai.com"
        deepseek = urlparse(cfg.base_url).hostname == "api.deepseek.com"
        if kwargs.get("json_object") and (mode == "on" or (mode == "auto" and (official or deepseek))):
            request["response_format"] = {"type": "json_object"}
        if deepseek and cfg.model_name in ("deepseek-flash", "deepseek-v4-pro"):
            request["reasoning_effort"] = kwargs["reasoning_effort"]
        # Optional provider capability, kept off for incompatible gateways.
        if os.getenv("LLM_PROMPT_CACHE_KEY", "off") == "on":
            request["prompt_cache_key"] = "pptmaker-v2-" + self.role
        response = self._get_openai_client().chat.completions.create(**request)
        usage = getattr(response, "usage", None)
        details = getattr(usage, "prompt_tokens_details", None)
        output_details = getattr(usage, "completion_tokens_details", None)
        self._call_usage.value = {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "cached_input_tokens": (getattr(details, "cached_tokens", 0)
                                    or getattr(usage, "prompt_cache_hit_tokens", 0) or 0),
            "reasoning_tokens": getattr(output_details, "reasoning_tokens", 0) or 0,
            "usage_reported": usage is not None,
        }
        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise ValueError("LLM output was truncated; increase the stage token budget")
        return choice.message.content or ""

    def _chat_anthropic(self, messages: list, **kwargs) -> str:
        cfg = self.config.anthropic
        system = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
        converted = []
        for message in messages:
            if message.get("role") == "system":
                continue
            content = message.get("content", "")
            if isinstance(content, list):
                blocks = []
                for block in content:
                    if block.get("type") == "image_url":
                        url = block["image_url"]["url"]
                        header, data = url.split(",", 1)
                        blocks.append({"type": "image", "source": {"type": "base64",
                                       "media_type": header[5:].split(";")[0], "data": data}})
                    else:
                        blocks.append(deepcopy(block))
                content = blocks
            converted.append({"role": message.get("role", "user"), "content": content})
        if os.getenv("ANTHROPIC_PROMPT_CACHE", "off") == "on" and system:
            system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        response = self._get_anthropic_client().messages.create(
            model=cfg.model_name, system=system, messages=converted,
            temperature=kwargs["temperature"], max_tokens=min(kwargs["max_tokens"], cfg.max_tokens))
        usage = getattr(response, "usage", None)
        read = getattr(usage, "cache_read_input_tokens", 0) or 0
        write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        self._call_usage.value = {
            "input_tokens": (getattr(usage, "input_tokens", 0) or 0) + read + write,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cached_input_tokens": read, "cache_write_tokens": write,
            "usage_reported": usage is not None,
        }
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise ValueError("LLM output was truncated; increase the stage token budget")
        return "".join(b.text for b in response.content if getattr(b, "type", "text") == "text")

    def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs)

    def generate_with_image(self, prompt: str, image_base64: str, system: str = "", **kwargs) -> str:
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_base64}},
        ]})
        return self.chat(messages, **kwargs)


@lru_cache()
def get_llm_config() -> LLMConfig:
    """Get cached LLM configuration from environment."""
    return LLMConfig.from_env()


@lru_cache(maxsize=16)
def _configured_client(config_json: str, role: str) -> LLMClient:
    return LLMClient(LLMConfig.model_validate_json(config_json), role=role)


def get_llm_client(role: str = "default") -> LLMClient:
    """Reuse connections; optionally route stages to user-selected models."""
    config = get_llm_config().model_copy(deep=True)
    cfg = config.get_active_config()
    prefix = config.provider.upper() + "_" + role.upper()
    cfg.model_name = os.getenv(prefix + "_MODEL", cfg.model_name)
    return _configured_client(config.model_dump_json(), role)
