"""The server, rather than a browser's stage chain, owns workflow decisions."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.api.websocket import WorkflowRunner, _dispatch
from app.config import settings
from app.storage.memory import memory_store


@pytest.fixture
def workflow_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    return WorkflowRunner.create_project({"topic":"后端编排验收", "page_count":2})


def install_stages(monkeypatch, fail=None):
    calls = []
    for method, stage, status in (("cmd_parse_input","parse","parsed"),
                                  ("cmd_plan_outline","plan","planned"),
                                  ("cmd_generate_parallel","generate","completed"),
                                  ("cmd_render_pptx","render","completed")):
        def make_step(stage, status):
            async def step(self, pid):
                calls.append(stage)
                await asyncio.sleep(0)
                project = memory_store.get_project(pid)
                project["status"] = "failed" if fail == stage else status
                if stage == "plan" and fail != stage:
                    project["outline"] = [{"page_id":"p-1"}]
                    project["pages"] = [{"page_id":"p-1"}]
                if status == "completed" and fail != stage:
                    Path(settings.storage_path, pid+".pptx").write_bytes(b"fixture")
                memory_store.update_project(pid,project)
            return step
        monkeypatch.setattr(WorkflowRunner,method,make_step(stage,status))
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("status,outline,expected",[
    ("idle",False,["parse","plan","generate"]),
    ("parsed",False,["plan","generate"]),
    ("planned",True,["generate"]),
    ("failed",True,["generate"]),
    ("editing",True,["render"]),
    ("completed",True,["render"]),
])
async def test_server_selects_remaining_stages(workflow_project,monkeypatch,status,outline,expected):
    pid = workflow_project["id"]
    memory_store.update_project(pid,{"status":status,"outline":[{"page_id":"p-1"}] if outline else [],
                                    "pages":[{"page_id":"p-1"}] if outline else []})
    calls = install_stages(monkeypatch)
    await WorkflowRunner(pid,AsyncMock()).cmd_run_workflow(pid)
    assert calls == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,expected",[("parse",["parse"]),("plan",["parse","plan"])])
async def test_failure_stops_the_chain(workflow_project,monkeypatch,failure,expected):
    calls = install_stages(monkeypatch,fail=failure)
    pid = workflow_project["id"]
    await WorkflowRunner(pid,AsyncMock()).cmd_run_workflow(pid)
    assert calls == expected and memory_store.get_project(pid)["status"] == "failed"


@pytest.mark.asyncio
async def test_duplicate_requests_across_connections_do_not_rewrite_completed_work(workflow_project,monkeypatch):
    pid = workflow_project["id"]
    calls = install_stages(monkeypatch)
    send = AsyncMock()
    await asyncio.gather(WorkflowRunner(pid,send).cmd_run_workflow(pid),WorkflowRunner(pid,send).cmd_run_workflow(pid))
    assert calls == ["parse","plan","generate"]
    assert any(call.args[0]["type"] == "completed" for call in send.call_args_list)


@pytest.mark.asyncio
async def test_dispatch_supports_single_workflow_command(workflow_project,monkeypatch):
    runner = WorkflowRunner(workflow_project["id"],AsyncMock())
    run = AsyncMock()
    monkeypatch.setattr(WorkflowRunner,"cmd_run_workflow",run)
    await _dispatch({"type":"run_workflow"},workflow_project["id"],runner,runner.send)
    run.assert_awaited_once_with(workflow_project["id"])


@pytest.mark.asyncio
async def test_backend_job_outlives_the_connection_and_deduplicates_requests(workflow_project,monkeypatch):
    from app.api.websocket import manager
    started, release = asyncio.Event(), asyncio.Event()
    calls = []
    async def run(self,pid):
        calls.append(pid)
        started.set()
        await release.wait()
        memory_store.update_project(pid,{"status":"completed"})
    monkeypatch.setattr(WorkflowRunner,"cmd_run_workflow",run)
    pid = workflow_project["id"]
    connection_runner = WorkflowRunner(pid,AsyncMock())
    await _dispatch({"type":"run_workflow"},pid,connection_runner,connection_runner.send)
    await started.wait()
    task = manager.workflow_tasks[pid]
    connection_runner.cancel()  # Disconnect cancels only the connection's legacy runner.
    await _dispatch({"type":"run_workflow"},pid,connection_runner,connection_runner.send)
    assert calls == [pid] and not task.done()
    release.set()
    await task
    assert memory_store.get_project(pid)["status"] == "completed" and not manager.workflow_running(pid)
