"""Persistence, history access, privilege boundaries, and atomic output budgets."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.storage.memory import memory_store
from app.storage.account_repository import AccountRepository, QuotaExceeded

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_DB", str(tmp_path / "account.sqlite3"))
    monkeypatch.setattr(settings, "storage_path", str(tmp_path / "exports"))
    memory_store._projects.clear()
    yield TestClient(app)
    memory_store._projects.clear()

def test_profile_persists_and_preferences_merge(client, tmp_path):
    original = client.get("/api/v1/account").json()
    updated = client.patch("/api/v1/account/profile", json={"display_name":"林间", "email":"author@example.com", "preferences":{"style":"学术简约"}})
    assert updated.status_code == 200
    saved = AccountRepository(str(tmp_path / "account.sqlite3")).profile()
    assert saved["display_name"] == "林间"
    assert saved["account_id"] == original["profile"]["account_id"]
    assert saved["preferences"] == {"style":"学术简约", "page_count":8, "language":"zh-CN"}
    assert "api_key" not in updated.json()["account"]
    assert "api_key" not in updated.json()["profile"]
    assert updated.json()["account"]["authentication"] == "local_workspace"

@pytest.mark.parametrize("patch", [{"is_vip":True},{"account_id":"admin"},{"preferences":{"page_count":51}},{"display_name":"  "},{"email":"invalid"}])
def test_profile_rejects_privileged_or_invalid_fields(client, patch):
    assert client.patch("/api/v1/account/profile",json=patch).status_code == 422

def test_membership_is_backend_configured_and_expiry_enforced(client, monkeypatch):
    monkeypatch.setenv("FOLIO_MEMBERSHIP","plus")
    assert client.get("/api/v1/account/membership").json()["is_vip"]
    monkeypatch.setenv("FOLIO_MEMBERSHIP_EXPIRES_AT","2000-01-01T00:00:00Z")
    data = client.get("/api/v1/account/membership").json()
    assert data["status"] == "expired" and not data["is_vip"]

def test_history_search_favorite_archive_restore_and_snapshot(client):
    a = client.post("/api/v1/projects",json={"spec":{"topic":"研究报告", "page_count":4},"user_input":"原始资料"}).json()
    client.post("/api/v1/projects",json={"spec":{"topic":"产品说明"}})
    response = client.patch(f'/api/v1/projects/{a["id"]}',json={"favorite":True,"title":"新研究报告","tags":["研究","研究"]})
    assert response.status_code == 200
    assert response.json()["tags"] == ["研究"] and response.json()["preview_url"] is None
    result = client.get("/api/v1/projects",params={"q":"研究","favorite":True}).json()
    assert result["total"] == 1 and "user_input" not in result["projects"][0]
    assert client.get(f'/api/v1/projects/{a["id"]}').json()["user_input"] == "原始资料"
    assert client.get("/api/v1/workspace").json()["stats"]["favorites"] == 1
    client.patch(f'/api/v1/projects/{a["id"]}',json={"archived":True})
    assert client.get("/api/v1/projects").json()["total"] == 1
    assert client.get("/api/v1/projects?archived=true").json()["total"] == 1
    client.patch(f'/api/v1/projects/{a["id"]}',json={"archived":False})
    assert client.get("/api/v1/projects?page_size=1&page=2").json()["projects"]
    assert client.get("/api/v1/projects?page_size=51").status_code == 422
    assert client.get("/api/v1/projects/missing").status_code == 404

def test_download_requires_completed_project_and_existing_file(client, tmp_path):
    pid = client.post("/api/v1/projects",json={}).json()["id"]
    memory_store.update_project(pid,{"status":"completed"})
    assert client.get(f"/api/v1/projects/{pid}").json()["download_url"] is None
    directory = tmp_path / "exports"; directory.mkdir()
    (directory / (pid+".pptx")).write_bytes(b"sample")
    assert client.get(f"/api/v1/projects/{pid}").json()["download_url"] == f"/storage/{pid}.pptx"
    memory_store.update_project(pid,{"status":"editing"})
    assert client.get(f"/api/v1/projects/{pid}").json()["download_url"] is None

def test_usage_is_durable_idempotent_and_releases_reserved_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_MONTHLY_OUTPUT_LIMIT","100")
    repo = AccountRepository(str(tmp_path / "ledger.sqlite3")); repo.reserve_output("call",80)
    assert repo.usage()["quota"]["remaining"] == 20
    record = dict(call_id="call",created_at=datetime.now(timezone.utc).isoformat(),input_tokens=100,output_tokens=30,cached_input_tokens=60,success=True)
    repo.record_usage(record); repo.record_usage(record)
    data = AccountRepository(repo.path).usage()
    assert data["calls"] == 1 and data["output_tokens"] == 30
    assert data["provider_cache_hit_rate"] == .6
    assert data["quota"]["remaining"] == 70 and data["quota"]["reserved"] == 0

def test_parallel_reservations_cannot_overspend(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_MONTHLY_OUTPUT_LIMIT","100")
    repo = AccountRepository(str(tmp_path / "concurrent.sqlite3"))
    def reserve(index):
        try: repo.reserve_output(str(index),70); return True
        except QuotaExceeded: return False
    with ThreadPoolExecutor(max_workers=2) as pool: assert sorted(pool.map(reserve,[1,2])) == [False,True]
    assert repo.usage()["quota"]["reserved"] == 70

def test_exceeded_quota_stops_sdk_before_billable_call(tmp_path, monkeypatch):
    from app.llm.config import LLMClient, LLMConfig, OpenAIConfig
    monkeypatch.setenv("FOLIO_DB",str(tmp_path / "blocked.sqlite3")); monkeypatch.setenv("FOLIO_MONTHLY_OUTPUT_LIMIT","10")
    llm = LLMClient(LLMConfig(openai=OpenAIConfig(api_key="test"))); sdk_call = Mock(return_value="result")
    monkeypatch.setattr(llm,"_chat_openai",sdk_call)
    with pytest.raises(QuotaExceeded): llm.chat([{"role":"user","content":"hello"}],max_tokens=20)
    sdk_call.assert_not_called()
    assert AccountRepository(str(tmp_path / "blocked.sqlite3")).usage()["quota"]["reserved"] == 0

def test_reject_legacy_word_file(client):
    assert client.post("/api/v1/upload/parse",files={"file":("old.doc",b"binary","application/msword")}).status_code == 400

@pytest.mark.parametrize("count",[0,51,4.5,True])
def test_page_limit_enforced_at_api_boundary(client,count):
    assert client.post("/api/v1/projects",json={"spec":{"page_count":count}}).status_code == 422

def test_disconnect_does_not_leave_history_stuck_in_progress(client):
    pid = client.post("/api/v1/projects",json={}).json()["id"]
    with client.websocket_connect(f"/ws/{pid}") as socket:
        assert socket.receive_json()["type"] == "initial_state"
        memory_store.update_project(pid,{"status":"generating"})
    assert memory_store.get_project(pid)["status"] == "failed"
    assert "连接关闭" in memory_store.get_project(pid)["error"]
