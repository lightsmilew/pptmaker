"""Pytest configuration and shared fixtures."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is on the path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


def pytest_configure(config):
    """Keep test snapshots away from the user's persistent project history."""
    import uuid
    directory = BACKEND_ROOT / "storage" / "test-databases"
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["PPTMAKER_DB"] = str(directory / f"{uuid.uuid4().hex}.sqlite3")
    os.environ["FOLIO_DB"] = os.environ["PPTMAKER_DB"]
    os.environ["FOLIO_MONTHLY_OUTPUT_LIMIT"] = "0"
    os.environ["FOLIO_MEMBERSHIP"] = "local"
    os.environ.pop("FOLIO_MEMBERSHIP_EXPIRES_AT", None)
    temp_root = BACKEND_ROOT / "storage" / "test-runs"
    temp_root.mkdir(parents=True, exist_ok=True)
    if not config.option.basetemp:
        config.option.basetemp = str(temp_root / uuid.uuid4().hex)


# ============= Async Event Loop =============

@pytest.fixture
def authenticated_client():
    """Use real server sessions in API tests; no authentication bypass."""
    def make(email="author@example.test", name="测试作者"):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        response = client.post("/api/v1/auth/register", json={"email":email,"password":"Test-password-123","display_name":name},
                               headers={"X-Folio-Request":"1"})
        assert response.status_code == 201, response.text
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return client
    return make

@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============= Temporary directories =============

@pytest.fixture
def temp_dir():
    """Provide a clean temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def storage_dir(temp_dir):
    """Provide a temporary storage directory."""
    storage = temp_dir / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage


@pytest.fixture
def preview_dir(storage_dir):
    """Provide a temporary preview directory."""
    preview = storage_dir / "previews"
    preview.mkdir(parents=True, exist_ok=True)
    return preview


# ============= Environment =============

@pytest.fixture
def mock_env(monkeypatch, temp_dir):
    """Mock environment variables for testing."""
    env_file = temp_dir / ".env"
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "18000")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("STORAGE_PATH", str(temp_dir / "storage"))
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

    # Clear cached config
    from app.llm.config import get_llm_config
    get_llm_config.cache_clear()

    return {
        "storage": str(temp_dir / "storage"),
    }


# ============= LLM Mocks =============

class MockLLMClient:
    """Mock LLM client that returns predictable JSON responses."""

    def __init__(self, responses: Optional[List[Any]] = None):
        self.responses = responses or []
        self.call_count = 0
        self.calls: List[Dict[str, Any]] = []
        self.provider = "mock"

    def generate(self, prompt: str, system: str = "", max_tokens: int = 4096, **kwargs) -> str:
        """Return next pre-configured response."""
        self.calls.append({
            "prompt": prompt,
            "system": system,
            "max_tokens": max_tokens,
            **kwargs,
        })

        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            if isinstance(response, (dict, list)):
                import json
                return json.dumps(response, ensure_ascii=False)
            return str(response)

        # Default: simple approval
        return '{"status": "approved", "score": 88}'

    def generate_with_image(self, prompt: str, image_base64: str, system: str = "", max_tokens: int = 4096) -> str:
        """Mock image-aware generation."""
        return self.generate(prompt=prompt, system=system, max_tokens=max_tokens, image=image_base64[:100])

    @property
    def config(self):
        """Provide a config attribute for compatibility."""
        return MagicMock(is_configured=MagicMock(return_value=True))


@pytest.fixture
def mock_llm():
    """Provide a configurable mock LLM client."""
    client = MockLLMClient()
    import app.llm
    # Patch the source module
    patches = [
        patch("app.llm.config.get_llm_client", return_value=client),
        patch("app.llm.get_llm_client", return_value=client),
    ]
    for p in patches:
        p.start()
    # Also overwrite on each importer module (since `from X import Y` creates local binding)
    for module_name in [
        "app.agent.nodes.parser",
        "app.agent.nodes.planner",
        "app.agent.nodes.writer",
        "app.agent.nodes.designer",
        "app.agent.nodes.critic",
        "app.agent.nodes.revision_planner",
        "app.agent.nodes.global_reviewer",
    ]:
        try:
            mod = __import__(module_name, fromlist=["get_llm_client"])
            mod.get_llm_client = lambda *a, **kw: client
        except (ImportError, AttributeError):
            pass

    yield client
    for p in patches:
        p.stop()


@pytest.fixture
def mock_llm_with_responses():
    """Factory fixture for creating mock LLM with specific responses."""
    import app.llm
    patchers = []

    def _make(responses: List[Any]):
        client = MockLLMClient(responses)
        patches = [
            patch("app.llm.config.get_llm_client", return_value=client),
            patch("app.llm.get_llm_client", return_value=client),
        ]
        for p in patches:
            p.start()
            patchers.append(p)
        # Also overwrite on each importer module
        for module_name in [
            "app.agent.nodes.parser",
            "app.agent.nodes.planner",
            "app.agent.nodes.writer",
            "app.agent.nodes.designer",
            "app.agent.nodes.critic",
            "app.agent.nodes.revision_planner",
            "app.agent.nodes.global_reviewer",
        ]:
            try:
                mod = __import__(module_name, fromlist=["get_llm_client"])
                mod.get_llm_client = lambda *a, **kw: client
            except (ImportError, AttributeError):
                pass
        return client

    yield _make

    # Clean up
    for p in patchers:
        try:
            p.stop()
        except Exception:
            pass


# ============= Sample data =============

@pytest.fixture
def sample_spec() -> Dict[str, Any]:
    """Sample project specification."""
    return {
        "topic": "Python 编程入门",
        "audience": "初学者",
        "page_count": 4,
        "style": "教育培训",
        "needs_cover": True,
        "needs_toc": True,
        "needs_summary": True,
        "needs_chart": False,
        "notes": "通俗易懂",
    }


@pytest.fixture
def sample_outline() -> List[Dict[str, Any]]:
    """Sample outline items."""
    return [
        {
            "page_id": "page-01",
            "page_type": "cover",
            "page_title": "Python 编程入门",
            "subtitle": "从零开始学习编程",
            "page_purpose": "课程封面",
            "key_points": ["欢迎学习", "课程介绍"],
            "suggest_layout": "极简封面",
        },
        {
            "page_id": "page-02",
            "page_type": "toc",
            "page_title": "课程目录",
            "subtitle": "",
            "page_purpose": "展示课程大纲",
            "key_points": ["变量与类型", "控制流", "函数", "模块"],
            "suggest_layout": "编号目录",
        },
        {
            "page_id": "page-03",
            "page_type": "content",
            "page_title": "变量与数据类型",
            "subtitle": "基础概念",
            "page_purpose": "介绍基本数据类型",
            "key_points": ["整数", "浮点数", "字符串", "布尔值"],
            "suggest_layout": "左右双栏",
        },
        {
            "page_id": "page-04",
            "page_type": "conclusion",
            "page_title": "课程总结",
            "subtitle": "",
            "page_purpose": "总结本次课程",
            "key_points": ["回顾要点", "后续学习"],
            "suggest_layout": "结论重点",
        },
    ]


@pytest.fixture
def sample_pages_data() -> List[Dict[str, Any]]:
    """Sample pages data (legacy format)."""
    return [
        {
            "page_id": 1,
            "page_type": "cover",
            "title": "封面",
            "key_points": ["欢迎"],
            "bullet_points": ["Python 编程入门"],
            "status": "completed",
        },
        {
            "page_id": 2,
            "page_type": "content",
            "title": "内容",
            "key_points": ["要点1", "要点2"],
            "bullet_points": ["说明1", "说明2"],
            "status": "completed",
        },
    ]


@pytest.fixture
def sample_layout() -> Dict[str, Any]:
    """Sample layout JSON."""
    return {
        "theme_name": "academic_simple",
        "master": {
            "background": {"type": "solid", "rgb": [255, 255, 255]},
            "logo": {"enable": False},
            "color_scheme": {
                "primary": [20, 40, 80],
                "secondary": [80, 100, 140],
                "accent": [60, 120, 180],
                "text": [30, 30, 30],
                "light_text": [255, 255, 255],
            },
            "font_scheme": {
                "title_font": "Microsoft YaHei",
                "body_font": "Microsoft YaHei",
                "title_size": 32,
                "body_size": 16,
            },
        },
        "layouts": [
            {
                "layout_id": "content",
                "layout_type": "title_content",
                "placeholders": [
                    {"name": "title", "type": "title", "x": 0.8, "y": 0.4, "w": 11.7, "h": 0.8},
                    {"name": "content", "type": "text", "x": 1.0, "y": 1.6, "w": 11.2, "h": 5.2},
                ],
            }
        ],
    }


@pytest.fixture
def sample_review_result() -> Dict[str, Any]:
    """Sample review result."""
    return {
        "status": "approved",
        "score": 88,
        "dimensions": {
            "alignment": 9,
            "balance": 8,
            "readability": 9,
            "hierarchy": 8,
            "density": 9,
            "consistency": 9,
        },
        "issues": [],
        "next_action": "approve",
    }
