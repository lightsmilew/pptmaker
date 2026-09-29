"""Tests for planner node."""

import json
import pytest

from app.agent.nodes.planner import planner_node, generate_outline
from app.agent.state import create_initial_state
from app.models.page import PageType


class TestPlannerNode:
    """Tests for planner_node."""

    def test_plan_with_mock(self, mock_llm_with_responses, sample_spec):
        """Planner generates outline with mocked LLM."""
        outline_data = [
            {
                "page_id": "page-01",
                "page_type": "cover",
                "page_title": "封面",
                "subtitle": "副标题",
                "page_purpose": "介绍",
                "key_points": ["要点1", "要点2"],
                "suggest_layout": "极简封面",
            },
            {
                "page_id": "page-02",
                "page_type": "content",
                "page_title": "内容",
                "subtitle": "",
                "page_purpose": "说明",
                "key_points": ["a", "b"],
                "suggest_layout": "左右双栏",
            },
        ]
        client = mock_llm_with_responses([outline_data])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )

        result_state = planner_node(state)

        assert len(result_state["outline"]) == 2
        assert "page-01" in result_state["pages"]
        assert "page-02" in result_state["pages"]
        assert result_state["current_page_id"] == "page-01"
        # Pages initialized
        assert result_state["pages"]["page-01"].page_type == PageType.COVER
        assert result_state["pages"]["page-02"].page_type == PageType.CONTENT
        assert "page-01" in result_state["pages"]
        assert "page-02" in result_state["pages"]
        assert result_state["current_page_id"] == "page-01"
        # Pages initialized
        assert result_state["pages"]["page-01"].page_type == PageType.COVER
        assert result_state["pages"]["page-02"].page_type == PageType.CONTENT

    def test_plan_with_dict_wrapper(self, mock_llm_with_responses, sample_spec):
        """Planner handles wrapped dict response."""
        client = mock_llm_with_responses([{
            "pages": [
                {
                    "page_id": "page-01",
                    "page_type": "cover",
                    "page_title": "Cover",
                    "key_points": ["a"],
                    "suggest_layout": "极简封面",
                }
            ]
        }])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )

        result_state = planner_node(state)
        assert len(result_state["outline"]) == 1

    def test_plan_handles_invalid_page_type(self, mock_llm_with_responses, sample_spec):
        """Invalid page type falls back to content."""
        client = mock_llm_with_responses([[
            {
                "page_id": "page-01",
                "page_type": "invalid_type",  # Invalid
                "page_title": "Test",
                "key_points": ["a"],
                "suggest_layout": "标题正文",
            }
        ]])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )

        result_state = planner_node(state)
        # Should fallback to CONTENT
        assert result_state["pages"]["page-01"].page_type == PageType.CONTENT


class TestGenerateOutlineFunction:
    """Tests for standalone generate_outline function."""

    def test_generate_outline(self, mock_llm_with_responses):
        """Standalone generate_outline returns list."""
        client = mock_llm_with_responses([[
            {"page_id": "p1", "page_type": "cover", "page_title": "T", "key_points": [], "suggest_layout": "极简封面"},
            {"page_id": "p2", "page_type": "content", "page_title": "T2", "key_points": [], "suggest_layout": "标题正文"},
        ]])

        outline = generate_outline({"topic": "Test", "page_count": 2})
        assert len(outline) == 2
