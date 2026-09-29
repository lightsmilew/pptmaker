"""
Deep debugging: trace exactly what planner_node returns.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.agent.nodes import planner_node
from app.agent.state import create_initial_state


def test_planner_direct():
    """Call planner_node directly to see what it produces."""
    spec = {
        "topic": "Test Topic",
        "audience": "Students",
        "page_count": 3,
        "style": "简约",
        "needs_cover": True,
        "needs_toc": True,
        "needs_summary": True,
        "needs_chart": False,
        "notes": "Test requirement for integration testing",
    }
    user_input = "Test requirement for integration testing"

    state = create_initial_state(
        project_id="debug_proj",
        spec=spec,
        user_input=user_input,
    )

    print(f"Initial state outline: {state.get('outline')}")
    print(f"Initial state project status: {state['project'].status}")

    print("\nCalling planner_node (this will make an LLM call)...")
    try:
        result_state = planner_node(state)
        print(f"\nAfter planner_node:")
        print(f"  Outline length: {len(result_state.get('outline') or [])}")
        print(f"  Project status: {result_state['project'].status}")
        print(f"  Errors: {result_state.get('errors')}")
        print(f"  Workflow node: {result_state.get('workflow', {}).current_node}")
        if result_state.get('outline'):
            print(f"  First page: {result_state['outline'][0].get('page_title')[:30]}")
            return True
        else:
            return False
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_planner_direct()
