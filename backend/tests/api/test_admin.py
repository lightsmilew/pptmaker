"""Real administrator login, separation, policy enforcement, and secret-safe operations."""
import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage.auth_repository import AuthRepository, ADMIN_COOKIE, SESSION_COOKIE
from app.storage.admin_repository import AdminRepository
from app.storage.account_repository import account_repository, QuotaExceeded
from app.storage.memory import memory_store
from app.storage.sqlite_repository import ProjectRepository
from app import admin_config


@pytest.fixture
def clients(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_DB", str(tmp_path / "admin.sqlite3"))
    monkeypatch.setenv("FOLIO_ENV_FILE", str(tmp_path / "folio.env"))
    for field in admin_config.FIELDS:
        monkeypatch.setenv(field["key"], os.getenv(field["key"], field["default"]))
    monkeypatch.setenv("FOLIO_COOKIE_SECURE", "false")
    monkeypatch.setenv("FOLIO_REGISTRATION_ENABLED", "true")
    memory_store._projects.clear()
    monkeypatch.setattr(memory_store, "_repository", ProjectRepository())
    repo = AuthRepository()
    admin_id = repo.create_admin("admin@example.test", "Admin-password-123")
    admin, user = TestClient(app), TestClient(app)
    for client in (admin,user):
        client.headers["X-Folio-Request"] = "1"
    user_data = user.post("/api/v1/auth/register", json={"email":"writer@example.test","password":"User-password-123","display_name":"Writer"}).json()
    user.headers["X-CSRF-Token"] = user_data["csrf_token"]
    admin_data = admin.post("/api/v1/admin/login", json={"email":"admin@example.test","password":"Admin-password-123"}).json()
    admin.headers["X-CSRF-Token"] = admin_data["csrf_token"]
    yield admin, user, admin_id, user_data["account"]["profile"]["account_id"]
    admin.close(); user.close(); memory_store._projects.clear()


def test_admin_login_accepts_bootstrap_password_without_relaxing_new_password_policy(clients):
    AuthRepository().create_admin("bootstrap@example.test", "smile")
    with TestClient(app, headers={"X-Folio-Request": "1"}) as client:
        result = client.post("/api/v1/admin/login", json={"email": "bootstrap@example.test", "password": "smile"})
        assert result.status_code == 200
        client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
        assert client.post("/api/v1/admin/password", json={"current_password": "smile", "new_password": "short"}).status_code == 422
        assert client.post("/api/v1/auth/register", json={"email": "short@example.test", "password": "smile", "display_name": "Short"}).status_code == 422
        assert client.post("/api/v1/admin/login", json={"email": "bootstrap@example.test", "password": "wrong"}).status_code == 401


def test_separate_admin_identity_cookie_scope_and_login(clients):
    admin,user,aid,uid = clients
    assert aid != uid
    cookie = admin.cookies.get(ADMIN_COOKIE)
    assert cookie and not admin.cookies.get(SESSION_COOKIE)
    assert any(c.path == "/api/v1/admin" for c in admin.cookies.jar)
    assert user.get("/api/v1/admin/overview").status_code == 401
    user.cookies.set(ADMIN_COOKIE, user.cookies.get(SESSION_COOKIE))
    assert user.get("/api/v1/admin/overview").status_code == 401
    admin.cookies.set(SESSION_COOKIE,cookie)
    assert admin.get("/api/v1/account").status_code == 401
    anonymous=TestClient(app,headers={"X-Folio-Request":"1"})
    assert anonymous.post("/api/v1/auth/login",json={"email":"admin@example.test","password":"Admin-password-123"}).status_code == 401
    assert anonymous.post("/api/v1/admin/login",json={"email":"writer@example.test","password":"User-password-123"}).status_code == 401
    records=admin.get("/api/v1/admin/records?kind=login").json()["items"]
    assert len(records)==4 and sum(r["success"] for r in records)==2
    assert all("password" not in r and "token_hash" not in r for r in records)


def test_csrf_origin_and_public_privilege_escalation(clients):
    admin,user,_,uid=clients
    assert admin.patch(f"/api/v1/admin/users/{uid}",headers={"X-CSRF-Token":"bad"},json={"tier":"pro"}).status_code == 403
    assert admin.patch(f"/api/v1/admin/users/{uid}",headers={"Origin":"https://evil.test"},json={"tier":"pro"}).status_code == 403
    assert user.patch("/api/v1/account/profile",json={"role":"admin","membership":{"tier":"studio"}}).status_code == 422
    assert admin.patch(f"/api/v1/admin/users/{uid}",json={"role":"admin"}).status_code == 422
    assert admin.patch(f"/api/v1/admin/users/{uid}",json={"tier":None}).status_code == 422


def test_default_plans_limits_upgrade_expiration_and_budget(clients):
    admin,user,_,uid=clients
    account=user.get("/api/v1/account").json()
    assert account["membership"]["name"] == "普通会员"
    assert account["membership"]["limits"] == {"max_pages":20,"concurrency":1}
    assert account["usage"]["quota"]["limit"] == 50000
    assert user.post("/api/v1/projects",json={"spec":{"topic":"限额","page_count":21}}).status_code == 403
    assert user.patch("/api/v1/account/profile",json={"preferences":{"page_count":21}}).status_code == 403
    pid=user.post("/api/v1/projects",json={"spec":{"page_count":8}}).json()["id"]
    with user.websocket_connect(f"/ws/{pid}") as socket:
        socket.receive_json()
        socket.send_json({"type":"update_spec","data":{"patch":{"page_count":21}}})
        assert socket.receive_json()["type"] == "error"
    assert admin.patch(f"/api/v1/admin/users/{uid}",json={"tier":"pro"}).status_code == 200
    assert user.post("/api/v1/projects",json={"spec":{"page_count":50}}).status_code == 200
    assert admin.patch(f"/api/v1/admin/users/{uid}",json={"expires_at":"2020-01-01T00:00:00Z"}).status_code == 200
    assert not user.get("/api/v1/account").json()["membership"]["is_vip"]
    assert user.post("/api/v1/projects",json={"spec":{"page_count":21}}).status_code == 403
    admin.patch(f"/api/v1/admin/users/{uid}",json={"monthly_output_limit":100})
    repo=account_repository(uid)
    repo.reserve_output("first",80)
    with pytest.raises(QuotaExceeded): repo.reserve_output("second",30)
    admin.patch(f"/api/v1/admin/users/{uid}",json={"monthly_output_limit":None})
    assert repo.output_limit()==50000


def test_plan_edit_and_disabled_user_revoke_real_sessions(clients):
    admin,user,_,uid=clients
    plan=admin.get("/api/v1/admin/memberships").json()["items"][0]
    plan.pop("tier"); plan.update(max_pages=10,monthly_output_limit=12000)
    assert admin.patch("/api/v1/admin/memberships/basic",json=plan).status_code == 200
    assert user.post("/api/v1/projects",json={"spec":{"page_count":11}}).status_code == 403
    assert admin.patch(f"/api/v1/admin/users/{uid}",json={"status":"disabled"}).status_code == 200
    assert user.get("/api/v1/account").status_code == 401
    assert admin.get("/api/v1/admin/users?status=disabled").json()["total"] == 1
    assert admin.get("/api/v1/admin/users?q=absent").json()["items"] == []


def test_reset_and_admin_password_rotation(clients):
    admin,user,aid,uid=clients
    result=admin.post(f"/api/v1/admin/users/{uid}/reset-password").json()
    assert len(result["temporary_password"]) >= 24
    assert user.get("/api/v1/account").status_code == 401
    assert AuthRepository().authenticate("writer@example.test",result["temporary_password"])==uid
    old=admin.cookies.get(ADMIN_COOKIE)
    result=admin.post("/api/v1/admin/password",json={"current_password":"Admin-password-123","new_password":"New-admin-password-456"})
    assert result.status_code==200 and not AuthRepository().session(old)
    admin.headers["X-CSRF-Token"]=result.json()["csrf_token"]
    assert admin.get("/api/v1/admin/session").status_code==200
    assert AuthRepository().authenticate("admin@example.test","New-admin-password-456","admin")==aid


def test_config_atomic_write_only_allowlist_conflict_and_busy(clients):
    admin,user,_,_=clients
    path=admin_config.environment_path()
    path.write_text("# keep this comment\nUNMANAGED=keep\nOPENAI_API_KEY=old\n",encoding="utf8")
    before=admin.get("/api/v1/admin/config").json()
    secret="new-secret-for-isolated-test"
    changes={"OPENAI_API_KEY":secret,"OPENAI_MODEL":"isolated-model","OPENAI_WRITER_MODEL":""}
    response=admin.patch("/api/v1/admin/config",json={"revision":before["revision"],"changes":changes})
    assert response.status_code==200
    assert secret not in response.text
    assert "# keep this comment" in path.read_text() and "UNMANAGED=keep" in path.read_text()
    assert os.environ["OPENAI_API_KEY"]==secret
    assert admin.patch("/api/v1/admin/config",json={"revision":before["revision"],"changes":{"OPENAI_MODEL":"other"}}).status_code==409
    revision=response.json()["revision"]
    for change in [{"FOLIO_DB":"/tmp/other"},{"OPENAI_API_KEY":"bad\nINJECT=value"},{"OPENAI_BASE_URL":"https://user:pass@api.example.test"},{"PPT_CONCURRENCY":"0"}]:
        assert admin.patch("/api/v1/admin/config",json={"revision":revision,"changes":change}).status_code==422
    pid=user.post("/api/v1/projects",json={}).json()["id"]
    memory_store.update_project(pid,{"status":"generating"})
    assert admin.patch("/api/v1/admin/config",json={"revision":revision,"changes":{"OPENAI_MODEL":"other"}}).status_code==409
    assert secret not in admin.get("/api/v1/admin/records?kind=admin").text


def test_records_overview_and_usage_are_durable_without_prompts(clients):
    admin,user,_,uid=clients
    pid=user.post("/api/v1/projects",json={"user_input":"private prompt"}).json()["id"]
    memory_store.update_project(pid,{"status":"completed"})
    account_repository(uid).record_usage(dict(call_id="actual-call",created_at=datetime.now(timezone.utc).isoformat(),project_id=pid,role="writer",model="test-model",provider="openai",input_tokens=40,output_tokens=20,cached_input_tokens=10,success=True,usage_reported=True))
    report=admin.get("/api/v1/admin/usage").json()
    assert report["summary"]["output_tokens"]==20 and report["provider_cache_hit_rate"]==.25
    assert admin.get("/api/v1/admin/overview").json()["users"]==1
    assert admin.get("/api/v1/admin/generations").json()["items"][0]["id"]==pid
    assert admin.get("/api/v1/admin/records?kind=generation").json()["total"]==2
    assert admin.get("/api/v1/admin/records?kind=usage").json()["total"]==1
    for kind in ("calls","generation","usage","admin","login"):
        body=admin.get("/api/v1/admin/records?kind="+kind).text
        assert "private prompt" not in body and "password_hash" not in body and "csrf" not in body
    assert admin.get("/api/v1/admin/usage?period=wrong").status_code==422


def test_provider_balance_is_real_or_explicitly_unsupported(clients,monkeypatch):
    admin,_,_,_=clients
    from app.llm.config import LLMConfig, OpenAIConfig
    config=LLMConfig(openai=OpenAIConfig(api_key="isolated-key",base_url="https://api.deepseek.com"))
    monkeypatch.setattr("app.llm.config.get_llm_config",lambda:config)
    mock=AsyncMock()
    mock.__aenter__.return_value=mock
    mock.get.return_value=httpx.Response(200,request=httpx.Request("GET","https://api.deepseek.com/user/balance"),json={"is_available":True,"balance_infos":[{"currency":"CNY","total_balance":"12.30","granted_balance":"2.30","topped_up_balance":"10.00"}]})
    monkeypatch.setattr("app.api.admin.httpx.AsyncClient",lambda **kwargs:mock)
    result=admin.post("/api/v1/admin/provider/balance")
    assert result.status_code==200 and result.json()["balances"][0]["total_balance"]=="12.30"
    assert mock.get.call_args.args[0]=="https://api.deepseek.com/user/balance"
    config.openai.base_url="https://other.example.test/v1"
    assert not admin.post("/api/v1/admin/provider/balance").json()["supported"]


def test_registration_toggle_and_scope_safe_bootstrap(clients,tmp_path):
    admin,user,_,uid=clients
    config=admin.get("/api/v1/admin/config").json()
    result=admin.patch("/api/v1/admin/config",json={"revision":config["revision"],"changes":{"FOLIO_REGISTRATION_ENABLED":"false"}})
    assert result.status_code==200
    assert TestClient(app,headers={"X-Folio-Request":"1"}).post("/api/v1/auth/register",json={"email":"new@example.test","password":"Password-123456","display_name":"New"}).status_code==403
    from app.cli import create_admin
    path=tmp_path / "new-admin.txt"
    create_admin(["--email","new-admin@example.test","--credentials-file",str(path)])
    assert "Password:" in path.read_text() and AuthRepository().user(uid)["role"]=="user"
    duplicate=tmp_path / "duplicate.txt"
    with pytest.raises(SystemExit): create_admin(["--email","writer@example.test","--credentials-file",str(duplicate)])
    assert not duplicate.exists()
    assert AuthRepository().authenticate("writer@example.test","User-password-123")==uid
