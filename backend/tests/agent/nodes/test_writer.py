"""Tests for writer node."""

import json
import pytest

from app.agent.nodes.writer import writer_node, generate_page_content
from app.agent.state import create_initial_state
from app.models.page import PageState, PageType, PageStatus


class TestWriterNode:
    """Tests for writer_node."""

    def test_write_page(self, mock_llm_with_responses, sample_spec):
        """Writer generates page content."""
        client = mock_llm_with_responses([{
            "title": "Python 数据类型",
            "subtitle": "基础概念",
            "key_points": ["整数", "浮点数", "字符串"],
            "bullet_points": ["整数是没有小数部分的数字", "浮点数可以有小数"],
            "speaker_notes": "讲解基本数据类型",
        }])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        # Set up page
        page = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            title="",
            key_points=[],
        )
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"

        # Set outline
        state["outline"] = [
            {
                "page_id": "page-01",
                "page_type": "content",
                "page_title": "Python 数据类型",
                "subtitle": "",
                "key_points": ["a", "b"],
                "suggest_layout": "标题正文",
            }
        ]

        result_state = writer_node(state)

        page_after = result_state["pages"]["page-01"]
        assert page_after.title == "Python 数据类型"
        assert len(page_after.key_points) == 3
        assert len(page_after.bullet_points) == 2

    def test_write_page_no_current(self, mock_llm, sample_spec):
        """Writer handles no current page."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        # No current page
        result_state = writer_node(state)
        # Should not error
        assert result_state is not None

    def test_write_page_no_outline_match(self, mock_llm, sample_spec):
        """Writer handles missing outline gracefully."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        page = PageState(page_id="page-99")  # No matching outline
        state["pages"]["page-99"] = page
        state["current_page_id"] = "page-99"
        state["outline"] = []

        result_state = writer_node(state)
        assert result_state["pages"]["page-99"].status == PageStatus.FAILED


class TestGeneratePageContentFunction:
    """Tests for standalone generate_page_content."""

    def test_generate_content(self, mock_llm_with_responses):
        """Standalone content generation."""
        client = mock_llm_with_responses([{
            "title": "Test",
            "subtitle": "",
            "key_points": ["k1", "k2"],
            "bullet_points": ["b1"],
            "speaker_notes": "notes",
        }])

        result = generate_page_content(
            page_id="p1",
            page_type="content",
            page_title="Test",
            subtitle="",
            topic="Test Topic",
            key_points=["k1", "k2"],
        )
        assert result["title"] == "Test"
        assert len(result["key_points"]) == 2
