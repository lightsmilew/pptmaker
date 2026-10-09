"""Review advice must not destroy a renderable presentation."""

from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from pptx import Presentation

from app.api.websocket import WorkflowRunner
from app.config import settings
from app.models.page import PageStatus
from app.storage.memory import memory_store


@pytest.fixture
def review_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    monkeypatch.setenv("PPT_MAX_REVIEW_ROUNDS", "2")
    project = WorkflowRunner.create_project({"topic":"检查恢复", "page_count":2, "style":"商务简约"})
    project.update(outline=[{"page_id":f"p-{i}", "page_type":"content", "page_title":f"标题 {i}",
                             "key_points":["具体观点"]} for i in (1,2)],
                   pages=[{"page_id":f"p-{i}", "page_type":"content", "status":"pending",
                           "content":{"title":f"标题 {i}", "key_points":["具体观点"], "bullet_points":[], "speaker_notes":""}}
                          for i in (1,2)])
    memory_store.update_project(project["id"], project)
    return project


def install_writer(monkeypatch, fail=None):
    calls = []
    def writer(state):
        page = state["pages"][state["current_page_id"]]
        calls.append(page.page_id)
        page.status = PageStatus.WRITING
        page.bullet_points = ["保留原文证据，不凭空增加事实。"]
        if page.page_id == fail:
            page.status = PageStatus.FAILED
            page.error = "模型请求未完成"
        return state
    monkeypatch.setattr("app.agent.nodes.writer_node", writer)
    return calls


def install_review(monkeypatch, scores=(60,), approve_last=False, content=False):
    counts = {}
    def critic(state):
        page = state["pages"][state["current_page_id"]]
        count = counts.get(page.page_id, 0)
        counts[page.page_id] = count+1
        page.status = PageStatus.REVIEWING
        page.review_method = "vision"
        page.review_status = "approved" if approve_last and count >= len(scores)-1 else "needs_revision"
        page.review_score = scores[min(count,len(scores)-1)]
        page.review_issues = [] if page.review_status == "approved" else [dict(issue_id="advice",category="readability",
            severity="medium",owner="content" if content else "layout",description="建议调整信息层级",suggested_action="简化表达")]
        return state
    monkeypatch.setattr("app.agent.nodes.critic_node",critic)
    return counts


@pytest.mark.asyncio
async def test_review_limit_exports_every_page_with_truthful_advice(review_project, monkeypatch):
    calls = install_writer(monkeypatch)
    counts = install_review(monkeypatch)
    send = AsyncMock()
    await WorkflowRunner(review_project["id"],send).cmd_generate_parallel(review_project["id"])
    saved = memory_store.get_project(review_project["id"])
    assert saved["status"] == "completed" and saved.get("error") is None
    assert set(calls) == {"p-1","p-2"} and len(calls) == 2
    assert counts == {"p-1":3,"p-2":3}  # first review plus two adjustments
    assert all(p["status"] == "completed" and p["review"]["status"] == "needs_revision" and
               p["review"]["warning"] and not p.get("error") for p in saved["pages"])
    assert len(Presentation(str(Path(settings.storage_path)/f'{saved["id"]}.pptx')).slides) == 2
    assert any(c.args[0]["type"] == "completed" for c in send.call_args_list)
    assert not any(c.args[0]["type"] == "error" for c in send.call_args_list)


@pytest.mark.asyncio
async def test_lower_score_does_not_stop_remaining_adjustment(review_project, monkeypatch):
    install_writer(monkeypatch)
    counts = install_review(monkeypatch,(60,40,90),approve_last=True)
    await WorkflowRunner(review_project["id"],AsyncMock()).cmd_generate_parallel(review_project["id"])
    saved = memory_store.get_project(review_project["id"])
    assert counts == {"p-1":3,"p-2":3}
    assert all(p["review"]["status"] == "approved" for p in saved["pages"])
    assert len({str(path) for path in Path(settings.storage_path).glob("previews/*/*/iteration-*.png")}) == 6


@pytest.mark.asyncio
async def test_failed_improvement_preserves_rendered_content_and_preview(review_project, monkeypatch):
    install_writer(monkeypatch)
    install_review(monkeypatch,content=True)
    original = None
    def fail_repair(state):
        nonlocal original
        page = state["pages"][state["current_page_id"]]
        original = deepcopy(page.to_dict())
        page.title = "不要保留失败调整"
        page.status = PageStatus.FAILED
        page.error = "调整调用失败"
        return state
    monkeypatch.setattr("app.agent.nodes.revision_planner_node",fail_repair)
    await WorkflowRunner(review_project["id"],AsyncMock()).cmd_generate_parallel(review_project["id"])
    saved = memory_store.get_project(review_project["id"])
    assert saved["status"] == "completed"
    assert all(p["content"]["title"] != "不要保留失败调整" and Path(p["preview"]["image_path"]).is_file() for p in saved["pages"])
    assert all("上一版" in p["review"]["warning"] for p in saved["pages"])


@pytest.mark.asyncio
async def test_retry_does_not_rewrite_approved_pages(review_project, monkeypatch):
    calls = install_writer(monkeypatch,fail="p-2")
    install_review(monkeypatch,(100,),approve_last=True)
    runner = WorkflowRunner(review_project["id"],AsyncMock())
    await runner.cmd_generate_parallel(review_project["id"])
    saved = memory_store.get_project(review_project["id"])
    assert saved["status"] == "failed" and "未能生成" in saved["error"]
    approved = deepcopy(saved["pages"][0])
    retry_calls = install_writer(monkeypatch)
    await runner.cmd_generate_parallel(review_project["id"])
    saved = memory_store.get_project(review_project["id"])
    assert saved["status"] == "completed" and retry_calls == ["p-2"]
    assert saved["pages"][0] == approved
    assert calls == ["p-1","p-2"]
    retry_calls.clear()
    await runner.cmd_generate_parallel(review_project["id"],force=True)
    assert set(retry_calls) == {"p-1","p-2"}


def test_vision_outage_falls_back_to_local_check_without_claiming_visual_approval(tmp_path, monkeypatch):
    from app.agent.state import create_initial_state
    from app.agent.nodes.critic import critic_node
    from app.models.page import PageState, PreviewInfo
    from app.tools.slide_scene import template_layout
    state = create_initial_state("fallback",{"topic":"测试", "review_mode":"vision"})
    page = PageState(page_id="p-1",title="明确标题",key_points=["观点"],layout_json=template_layout("content",1,False),
                     preview=PreviewInfo(image_path=str(tmp_path/"preview.png")))
    state["pages"][page.page_id] = page
    state["current_page_id"] = page.page_id
    def unavailable(*args,**kwargs):
        raise TimeoutError("vision offline")
    monkeypatch.setattr("app.agent.nodes.critic._review_page_image",unavailable)
    critic_node(state)
    assert page.review_status == "approved" and page.review_method == "local_geometry_fallback"
    assert "不代表视觉复核通过" in page.review_warning
    assert not page.error and not state["errors"]


def test_graph_finalizes_usable_page_without_changing_review_status():
    from app.agent.state import create_initial_state
    from app.agent.graph import route_page_review
    from app.agent.nodes.finalizer import finalizer_node
    from app.models.page import PageState, PreviewInfo
    from app.tools.slide_scene import template_layout
    state = create_initial_state("finalize",{"topic":"测试"})
    page = PageState(page_id="p-1",title="明确标题",review_status="needs_revision",
                     layout_json=template_layout("content",1,False),preview=PreviewInfo(image_path="preview.png"))
    state["pages"][page.page_id] = page
    state["current_page_id"] = page.page_id
    state["critic_iteration"] = 10
    assert route_page_review(state) == "finalize"
    finalizer_node(state)
    assert page.status == PageStatus.COMPLETED and page.review_status == "needs_revision"
    assert page.review_warning and not page.error


@pytest.mark.asyncio
async def test_manual_review_keeps_usable_page_completed_and_preserves_warning(review_project, monkeypatch):
    install_writer(monkeypatch)
    install_review(monkeypatch)
    send = AsyncMock()
    runner = WorkflowRunner(review_project["id"],send)
    await runner.cmd_generate_parallel(review_project["id"])
    await runner.cmd_trigger_review(review_project["id"],"p-1")
    saved = memory_store.get_project(review_project["id"])
    page = saved["pages"][0]
    assert saved["status"] == "completed" and page["status"] == "completed"
    assert page["review"]["status"] == "needs_revision" and page["review"]["warning"]
    review_events = [c.args[0]["data"] for c in send.call_args_list if c.args[0]["type"] == "review_completed"]
    assert review_events[-1]["warning"] == page["review"]["warning"]


@pytest.mark.asyncio
async def test_advice_survives_rest_and_authenticated_websocket_can_finish_recheck(review_project, monkeypatch, authenticated_client):
    client = authenticated_client("review-api@example.test")
    created = client.post("/api/v1/projects",json={"spec":{"topic":"审查建议", "page_count":2}}).json()
    memory_store.update_project(created["id"],{key:deepcopy(review_project[key]) for key in ("outline","pages")})
    calls = install_writer(monkeypatch)
    install_review(monkeypatch)
    await WorkflowRunner(created["id"],AsyncMock()).cmd_generate_parallel(created["id"])
    view = client.get(f'/api/v1/projects/{created["id"]}').json()
    assert view["status"] == "completed" and all(page["review"]["warning"] for page in view["pages"])
    assert client.get(f'/storage/{created["id"]}.pptx').status_code == 200
    saved = memory_store.get_project(created["id"])
    relative = Path(saved["pages"][0]["preview"]["image_path"]).relative_to(Path(settings.storage_path))
    assert client.get("/storage/"+relative.as_posix()).content.startswith(b"\x89PNG")
    # Existing runs used to classify review advice as generation failure. A
    # retry must recover that state without paying to rewrite usable pages.
    saved["status"] = "failed"
    saved["error"] = "部分页面未通过检查，请调整内容或重试"
    for page in saved["pages"]:
        page["status"] = "failed"
        page["error"] = "检查未通过"
    memory_store.update_project(created["id"],saved)
    from app.agent.nodes.critic import critic_node
    monkeypatch.setattr("app.agent.nodes.critic_node",critic_node)
    monkeypatch.setenv("PPT_REVIEW_MODE","local")
    csrf = client.headers["X-CSRF-Token"]
    with client.websocket_connect(f'/ws/{created["id"]}?csrf={csrf}',headers={"Origin":"http://127.0.0.1:5173"}) as ws:
        initial = ws.receive_json()
        assert initial["type"] == "initial_state" and initial["data"]["status"] == "failed"
        ws.send_json({"type":"generate_parallel"})
        for _ in range(100):
            event = ws.receive_json()
            assert event["type"] != "error", event
            if event["type"] == "completed":
                break
        else:
            pytest.fail("Expected completed after recheck")
    view = client.get(f'/api/v1/projects/{created["id"]}').json()
    assert view["status"] == "completed" and not view.get("error")
    assert all(page["review"]["status"] == "approved" and not page["review"].get("warning") for page in view["pages"])
    assert len(calls) == 2  # recheck reused both pages without another writing call
