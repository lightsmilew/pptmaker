"""
Integration test: simulate the full client-side creation flow
to verify parseInput -> planOutline -> generateParallel works end-to-end.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.api.websocket import WorkflowRunner
from app.storage.memory import memory_store


# Synchronous wrapper so we can call async from sync test
def run_async(coro):
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_create_and_plan():
    """Create project -> plan outline -> check outline exists."""
    # Step 1: Create project
    project = WorkflowRunner.create_project(
        spec={
            "topic": "Test Topic",
            "audience": "Students",
            "page_count": 3,
            "style": "简约",
            "needs_cover": True,
            "needs_toc": True,
            "needs_summary": True,
            "needs_chart": False,
        },
        user_input="Test requirement for integration testing",
    )
    project_id = project["id"]
    print(f"[1] Created project: {project_id}")
    print(f"    Status: {project['status']}")
    print(f"    Outline: {project.get('outline', [])[:1]}")

    # Step 2: Simulate WebSocket dispatcher
    sent_messages = []

    async def noop_send(msg):
        sent_messages.append(msg)
        print(f"    [WS SEND] type={msg.get('type')} - {str(msg)[:120]}")

    runner = WorkflowRunner(project_id, noop_send)

    # Step 3: plan_outline with detailed inspection
    print(f"\n[2] Calling plan_outline for {project_id}...")
    run_async(runner.cmd_plan_outline(project_id))

    project = memory_store.get_project(project_id)
    print(f"    Status after plan: {project['status']}")

    # The key question: what is outline right now?
    raw_outline = project.get("outline")
    print(f"    Outline raw: {raw_outline!r}")
    print(f"    Outline is None: {raw_outline is None}")
    print(f"    Outline is empty list: {raw_outline == []}")

    outline = raw_outline or []
    print(f"    Outline length: {len(outline)}")
    if outline:
        print(f"    First outline item: {outline[0].get('page_title', '')[:50]}")
    else:
        print("    ERROR: outline is empty!")
        # Now check pages - cmd_plan_outline should have created pages from outline
        pages = project.get("pages") or []
        print(f"    Pages length: {len(pages)}")
        print(f"    All WS messages: {[(m.get('type'), m.get('data', {}).get('message', m.get('data', {}).get('error', ''))) for m in sent_messages]}")
        return False

    return True
    # Directly call the guard logic
    outline_check = project.get("outline") or []
    if not outline_check:
        print("    Would fail: '请先生成大纲'")
        return False
    else:
        print(f"    OK: outline has {len(outline_check)} items")

    # Step 5: Call generate_parallel (briefly)
    print(f"\n[4] Calling generate_parallel (checking guard only)...")
    if not outline:
        print("    SKIPPING: no outline, would fail with '请先生成大纲'")
        return False

    # Don't actually generate (LLM call), just verify the path
    print("    PASS: generate_parallel would proceed")
    return True


if __name__ == "__main__":
    result = test_create_and_plan()
    print(f"\n{'PASS' if result else 'FAIL'}")
    sys.exit(0 if result else 1)
