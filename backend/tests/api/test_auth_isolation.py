"""Real cookie sessions and isolation of REST, WebSocket, files and metered calls."""
import json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest
from app.main import app
from app.config import settings
from app.storage.auth_repository import AuthRepository, SESSION_COOKIE, user_context
from app.storage.account_repository import AccountRepository, QuotaExceeded
from app.storage.memory import memory_store, MemoryStore


@pytest.fixture
def users(tmp_path, monkeypatch, authenticated_client):
    monkeypatch.setenv("FOLIO_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setattr(settings, "storage_path", str(tmp_path / "assets"))
    memory_store._projects.clear()
    from app.storage.sqlite_repository import ProjectRepository
    monkeypatch.setattr(memory_store, "_repository", ProjectRepository())
    a,b = authenticated_client("alice@example.test","Alice"),authenticated_client("bob@example.test","Bob")
    yield a,b
    memory_store._projects.clear()


def test_register_login_cookie_and_server_persistence(users):
    a,_ = users
    uid = a.get("/api/v1/auth/session").json()["account"]["profile"]["account_id"]
    with AuthRepository().connect() as db:
        stored = db.execute("SELECT password_hash FROM users WHERE id=?",(uid,)).fetchone()[0]
    assert stored.startswith("scrypt$") and "Test-password" not in stored
    fresh = TestClient(app)
    reply = fresh.post("/api/v1/auth/login",json={"email":"ALICE@example.test","password":"Test-password-123"},headers={"X-Folio-Request":"1"})
    assert reply.status_code == 200
    assert "HttpOnly" in reply.headers["set-cookie"] and "SameSite=strict" in reply.headers["set-cookie"]
    assert reply.json()["account"]["profile"]["account_id"] == uid
    a.patch("/api/v1/account/profile",json={"display_name":"Alice Updated","email":"contact@example.test"})
    assert fresh.get("/api/v1/account").json()["profile"]["display_name"] == "Alice Updated"
    assert fresh.get("/api/v1/account").json()["account"]["login_email"] == "alice@example.test"


def test_bad_login_duplicate_and_weak_registration(users):
    client = TestClient(app)
    headers={"X-Folio-Request":"1"}
    for email in ("alice@example.test","missing@example.test"):
        response = client.post("/api/v1/auth/login",json={"email":email,"password":"wrong-password"},headers=headers)
        assert response.status_code == 401 and response.json()["detail"] == "邮箱或密码不正确"
    assert client.post("/api/v1/auth/register",json={"email":"ALICE@example.test","password":"Test-password-123","display_name":"Another"},headers=headers).status_code == 409
    assert client.post("/api/v1/auth/register",json={"email":"c@example.test","password":"123","display_name":"C"},headers=headers).status_code == 422


def test_anonymous_access_and_csrf_origin_protection(users):
    a,_ = users
    anon=TestClient(app)
    for path in ("/api/v1/projects","/api/v1/workspace","/api/v1/account","/api/v1/account/usage","/storage/proj_any.pptx"):
        assert anon.get(path).status_code == 401
    assert anon.post("/api/v1/projects",json={}).status_code == 401
    assert a.post("/api/v1/projects",json={},headers={"X-CSRF-Token":"wrong"}).status_code == 403
    assert a.post("/api/v1/projects",json={},headers={"Origin":"https://evil.test"}).status_code == 403
    assert anon.post("/api/v1/auth/login",json={"email":"alice@example.test","password":"Test-password-123"}).status_code == 403
    assert anon.options("/api/v1/projects",headers={"Origin":"https://evil.test","Access-Control-Request-Method":"POST"}).status_code == 400


def test_other_user_cannot_read_modify_download_or_connect(users,tmp_path):
    a,b=users
    pid=a.post("/api/v1/projects",json={"spec":{"topic":"Alice private"},"user_input":"secret"}).json()["id"]
    assert a.get("/api/v1/projects").json()["total"] == 1
    assert b.get("/api/v1/projects").json()["total"] == 0
    assert b.get("/api/v1/workspace").json()["stats"]["total"] == 0
    assert b.get(f"/api/v1/projects/{pid}").status_code == 404
    assert b.patch(f"/api/v1/projects/{pid}",json={"title":"stolen"}).status_code == 404
    assert b.get(f"/api/v1/llm/usage?project_id={pid}").status_code == 404
    root=tmp_path/"assets"; root.mkdir(); (root/(pid+".pptx")).write_bytes(b"export")
    previews=root/"previews"/pid/"page-01"; previews.mkdir(parents=True); (previews/"iteration-01.png").write_bytes(b"image")
    for asset in (f"/storage/{pid}.pptx",f"/storage/previews/{pid}/page-01/iteration-01.png"):
        assert a.get(asset).status_code == 200
        assert b.get(asset).status_code == 404
    assert a.get("/storage/%2E%2E/app/main.py").status_code == 404
    with pytest.raises(WebSocketDisconnect) as exc:
        with b.websocket_connect(f"/ws/{pid}"):
            pass
    assert exc.value.code == 4404
    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect(f"/ws/{pid}"):
            pass
    assert exc.value.code == 4401


def test_logout_revokes_server_session_and_closes_active_socket(users):
    a,_=users
    pid=a.post("/api/v1/projects",json={}).json()["id"]
    old_token=a.cookies.get(SESSION_COOKIE)
    with a.websocket_connect(f"/ws/{pid}") as socket:
        assert socket.receive_json()["type"] == "initial_state"
        assert a.post("/api/v1/auth/logout").status_code == 204
        with pytest.raises(WebSocketDisconnect) as exc: socket.receive_json()
        assert exc.value.code == 4401
    replay=TestClient(app); replay.cookies.set(SESSION_COOKIE,old_token)
    assert replay.get("/api/v1/auth/session").status_code == 401


def test_password_change_revokes_other_sessions(users):
    a,_=users
    other=TestClient(app)
    other.post("/api/v1/auth/login",json={"email":"alice@example.test","password":"Test-password-123"},headers={"X-Folio-Request":"1"})
    old_token=other.cookies.get(SESSION_COOKIE)
    assert a.post("/api/v1/auth/password",json={"current_password":"wrong","new_password":"New-password-456"}).status_code == 400
    response=a.post("/api/v1/auth/password",json={"current_password":"Test-password-123","new_password":"New-password-456"})
    assert response.status_code == 200
    assert a.get("/api/v1/auth/session").status_code == 200
    assert AuthRepository().session(old_token) is None
    assert other.get("/api/v1/account").status_code == 401


def test_references_are_stored_on_server_and_owned(users,tmp_path):
    a,b=users
    upload=a.post("/api/v1/upload/parse",files={"file":("reference.txt","真实资料".encode(),"text/plain")}).json()
    assert upload["upload_id"] and "真实资料" in upload["content"]
    files=list((tmp_path/"assets"/"uploads").rglob("original.txt"))
    assert len(files)==1 and files[0].read_text(encoding="utf8")=="真实资料"
    refs=[{"upload_id":upload["upload_id"]},{"upload_id":upload["upload_id"]}]
    pid=a.post("/api/v1/projects",json={"uploaded_files":refs}).json()["id"]
    saved=a.get(f"/api/v1/projects/{pid}").json()
    assert saved["uploaded_files"][0]["content"]=="真实资料"
    assert len(saved["uploaded_files"]) == 1 and saved["user_input"].count("真实资料") == 1
    assert b.post("/api/v1/projects",json={"uploaded_files":refs}).status_code == 404
    assert a.post("/api/v1/projects",json={"uploaded_files":[{"content":"forged"}]}).status_code == 422
    assert a.get("/storage/uploads/any/original.txt").status_code == 404


def test_usage_quotas_and_memberships_are_independent(users,monkeypatch):
    a,b=users
    ids=[c.get("/api/v1/account").json()["profile"]["account_id"] for c in users]
    monkeypatch.setenv("FOLIO_MONTHLY_OUTPUT_LIMIT","100")
    ar,br=[AccountRepository(AuthRepository().path,uid) for uid in ids]
    ar.reserve_output("a",80); br.reserve_output("b",80)
    ar.record_usage(dict(call_id="a",created_at=datetime.now(timezone.utc).isoformat(),input_tokens=100,output_tokens=30,success=True))
    assert a.get("/api/v1/account/usage").json()["output_tokens"] == 30
    assert b.get("/api/v1/account/usage").json()["output_tokens"] == 0
    assert ar.usage()["quota"]["remaining"] == 70
    assert br.usage()["quota"]["remaining"] == 20
    with AuthRepository().connect() as db: db.execute("UPDATE users SET membership=?,output_limit=50 WHERE id=?",(json.dumps({"tier":"plus"}),ids[0]))
    assert a.get("/api/v1/account").json()["membership"]["is_vip"]
    assert not b.get("/api/v1/account").json()["membership"]["is_vip"]
    assert a.patch("/api/v1/account/profile",json={"membership":{"tier":"plus"},"output_limit":0}).status_code == 422


def test_project_step_attributes_actual_tokens_to_owner(users,monkeypatch):
    from app.llm.config import LLMClient, LLMConfig, OpenAIConfig
    from app.llm.telemetry import run_project_step
    a,b=users
    pid=a.post("/api/v1/projects",json={}).json()["id"]
    llm=LLMClient(LLMConfig(openai=OpenAIConfig(api_key="test")))
    def provider(messages, **kwargs):
        llm._call_usage.value={"input_tokens":20,"output_tokens":10,"usage_reported":True}
        return "ok"
    monkeypatch.setattr(llm,"_chat_openai",provider)
    run_project_step(lambda state: llm.chat([{"role":"user","content":"test"}],max_tokens=20),{},pid)
    assert a.get("/api/v1/account/usage").json()["output_tokens"]==10
    assert b.get("/api/v1/account/usage").json()["output_tokens"]==0
    assert user_context.get() is None
    assert b.get("/api/v1/llm/usage").json()["calls"]==0


def test_session_expiry_and_auth_throttle(users):
    a,_=users
    with AuthRepository().connect() as db: db.execute("UPDATE sessions SET expires_at=0")
    assert a.get("/api/v1/auth/session").status_code==401
    repo=AuthRepository()
    assert repo.throttle("login-test",1)
    assert not repo.throttle("login-test",1)


def test_project_profile_ledger_and_sessions_survive_repository_reload(users):
    a,b=users
    pid=a.post("/api/v1/projects",json={"spec":{"topic":"Durable"}}).json()["id"]
    uid=a.get("/api/v1/account").json()["profile"]["account_id"]
    a.patch("/api/v1/account/profile",json={"display_name":"Persistent"})
    repo=AccountRepository(AuthRepository().path,uid)
    repo.record_usage(dict(call_id="durable",created_at=datetime.now(timezone.utc).isoformat(),output_tokens=15,success=True))
    restored=MemoryStore()
    assert restored.get_project(pid)["owner_id"]==uid
    assert AccountRepository(repo.path,uid).profile()["display_name"]=="Persistent"
    assert AccountRepository(repo.path,uid).usage()["output_tokens"]==15
    assert AuthRepository(repo.path).session(a.cookies.get(SESSION_COOKIE))["user_id"]==uid


def test_ws_cannot_change_server_paths_or_bypass_page_limit(users):
    a,_=users
    pid=a.post("/api/v1/projects",json={}).json()["id"]
    memory_store.update_project(pid,{"pages":[{"page_id":"page-01","content":{},"status":"pending"}]})
    with a.websocket_connect(f"/ws/{pid}") as socket:
        socket.receive_json()
        socket.send_json({"type":"update_spec","data":{"patch":{"page_count":99999}}})
        assert socket.receive_json()["type"]=="error"
        socket.send_json({"type":"update_page","data":{"page_id":"page-01","patch":{"page_id":"../../other", "preview":{"image_path":"server-secret"}}}})
        assert socket.receive_json()["type"]=="error"
        assert memory_store.get_project(pid)["pages"][0]["page_id"]=="page-01"


def test_concurrent_budget_reservations_are_per_user(users,monkeypatch):
    monkeypatch.setenv("FOLIO_MONTHLY_OUTPUT_LIMIT","100")
    ids=[c.get("/api/v1/account").json()["profile"]["account_id"] for c in users]
    repos=[AccountRepository(AuthRepository().path,uid) for uid in ids]
    def reserve(pair):
        user,index=pair
        try: repos[user].reserve_output(f"{user}-{index}",70); return (user,True)
        except QuotaExceeded: return (user,False)
    with ThreadPoolExecutor(max_workers=4) as pool:
        result=list(pool.map(reserve,[(0,0),(1,0),(0,1),(1,1)]))
    for user in (0,1):
        assert sorted(ok for uid,ok in result if uid==user)==[False,True]
