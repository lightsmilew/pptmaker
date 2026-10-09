"""Allowlisted runtime configuration. API keys are write-only; file paths are server-owned."""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException
from dotenv import dotenv_values


def field(key, label, default, kind="text", group="connection", **options):
    return dict(key=key, label=label, default=str(default), kind=kind, group=group, **options)


FIELDS = [
    field("LLM_PROVIDER", "接口类型", "openai", "select", options=["openai", "anthropic"]),
    *[item for prefix, model, url in [("OPENAI", "gpt-4o-mini", "https://api.openai.com/v1"),
                                     ("ANTHROPIC", "claude-3-5-haiku-20241022", "https://api.anthropic.com/v1")]
      for item in [field(prefix+"_BASE_URL", prefix+" 接口地址", url, "url"),
                   field(prefix+"_API_KEY", prefix+" API Key", "", "secret"),
                   field(prefix+"_MODEL", prefix+" 默认模型", model),
                   field(prefix+"_TEMPERATURE", prefix+" 温度", "0.7", "number", minimum=0, maximum=2, step=0.1),
                   field(prefix+"_MAX_TOKENS", prefix+" 输出上限", "4096", "number", minimum=256, maximum=1048576)]],
    *[field(prefix+"_"+role+"_MODEL", prefix+" · "+label, "", group="routing")
      for prefix in ("OPENAI", "ANTHROPIC")
      for role, label in [("PARSER", "内容解析"), ("PLANNER", "大纲规划"), ("WRITER", "页面写作"), ("CRITIC", "视觉复核"), ("GLOBAL_REVIEWER", "全稿检查")]],
    field("DEEPSEEK_REASONING_EFFORT", "DeepSeek 思考强度", "none", "select", "routing", options=["none", "low", "medium", "high", "max"]),
    field("PPT_CONCURRENCY", "全局最大并行页数", 3, "number", "generation", minimum=1, maximum=8),
    field("PPT_MAX_REVIEW_ROUNDS", "检查后的调整轮数", 2, "number", "generation", minimum=1, maximum=4),
    field("PPT_REVIEW_MODE", "页面检查方式", "local", "select", "generation", options=["local", "vision"]),
    field("LLM_TIMEOUT_SECONDS", "接口超时（秒）", 90, "number", "generation", minimum=10, maximum=600),
    field("LLM_JSON_MODE", "结构输出模式", "auto", "select", "generation", options=["auto", "on", "off"]),
    field("LLM_PROMPT_CACHE_KEY", "提示缓存标识", "off", "select", "generation", options=["off", "on"]),
    field("ANTHROPIC_PROMPT_CACHE", "Anthropic 提示缓存", "off", "select", "generation", options=["off", "on"]),
    field("FOLIO_REGISTRATION_ENABLED", "开放用户注册", "true", "select", "access", options=["true", "false"]),
    field("FOLIO_SESSION_DAYS", "新会话有效期（天）", 7, "number", "access", minimum=1, maximum=30),
]
BY_KEY = {f["key"]: f for f in FIELDS}


def environment_path():
    return Path(os.getenv("FOLIO_ENV_FILE") or Path(__file__).resolve().parents[1] / ".env").resolve()


def revision():
    path = environment_path()
    return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()


def config_view():
    stored = dotenv_values(environment_path()) if environment_path().exists() else {}
    items = []
    for definition in FIELDS:
        key = definition["key"]
        value = os.getenv(key, definition["default"])
        items.append({**definition, "value": "" if definition["kind"] == "secret" else value,
                      "configured": bool(value) if definition["kind"] == "secret" else True,
                      "stored_differs": key in stored and stored[key] != value})
    return {"revision": revision(), "fields": items, "restart_required": False,
            "read_only": ["数据库与文件目录", "HTTPS Cookie 与请求来源", "监听地址与代理信任"]}


def validate(changes):
    if not changes or set(changes) - BY_KEY.keys():
        raise HTTPException(422, "只能修改页面列出的配置项")
    normalized = {}
    for key, value in changes.items():
        definition = BY_KEY[key]
        if not isinstance(value, str) or len(value) > 2048 or any(c in value for c in "\r\n\x00"):
            raise HTTPException(422, f"{definition['label']}格式无效")
        value = value.strip()
        if definition["kind"] == "select" and value not in definition["options"]:
            raise HTTPException(422, f"{definition['label']}选项无效")
        if definition["kind"] == "number":
            try:
                number = float(value)
                if not definition["minimum"] <= number <= definition["maximum"] or (definition.get("step", 1) == 1 and not number.is_integer()):
                    raise ValueError()
            except ValueError:
                raise HTTPException(422, f"{definition['label']}超出范围")
        if definition["kind"] == "url":
            parsed = urlparse(value)
            if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or
                (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")))):
                raise HTTPException(422, "接口地址需使用 HTTPS（本机调试可使用 HTTP），不能包含凭据或查询参数")
        if not value and definition["kind"] not in ("secret",) and not key.endswith("_MODEL"):
            raise HTTPException(422, f"{definition['label']}不能为空")
        if key in ("OPENAI_MODEL", "ANTHROPIC_MODEL") and not value:
            raise HTTPException(422, "默认模型不能为空")
        normalized[key] = value
    return normalized


def update_environment(changes, expected_revision):
    changes = validate(changes)
    if expected_revision != revision():
        raise HTTPException(409, "配置已被其他操作更新，请刷新后再保存")
    path = environment_path()
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    remaining = dict(changes)
    output = []
    for line in lines:
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match and match[1] in changes:
            if match[1] in remaining:
                output.append(match[1]+"="+json.dumps(remaining.pop(match[1]), ensure_ascii=False))
        else:
            output.append(line)
    output.extend(key+"="+json.dumps(value, ensure_ascii=False) for key, value in remaining.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temp = Path(handle.name)
            handle.write("\n".join(output)+"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    except OSError as exc:
        if temp:
            temp.unlink(missing_ok=True)
        raise HTTPException(503, "配置文件不可写，请检查部署目录权限") from exc
    os.environ.update(changes)
    from .llm.config import get_llm_config, _configured_client, _response_cache, _response_cache_lock
    get_llm_config.cache_clear()
    _configured_client.cache_clear()
    with _response_cache_lock:
        _response_cache.clear()
    return config_view()
