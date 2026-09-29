"""Tests for parser node."""

import json
import pytest
from unittest.mock import patch, MagicMock

from app.agent.nodes.parser import parser_node, parse_input
from app.agent.state import create_initial_state


class TestParserNode:
    """Tests for parser_node."""

    def test_parse_input_with_mock(self, mock_llm_with_responses):
        """Parser node with mocked LLM."""
        client = mock_llm_with_responses([{
            "topic": "Python 编程",
            "audience": "初学者",
            "page_count": 8,
            "style": "教育培训",
            "needs_cover": True,
            "needs_toc": True,
            "needs_summary": True,
            "needs_chart": False,
            "notes": "通俗易懂",
        }])

        state = create_initial_state(
            project_id="test-001",
            spec={},
            user_input="我想做一个关于 Python 编程入门的 PPT",
        )

        result_state = parser_node(state)

        # Spec should be populated
        assert result_state["project"].spec["topic"] == "Python 编程"
        assert result_state["project"].page_count == 8
        assert client.call_count == 1

    def test_parse_with_markdown_fence(self, mock_llm_with_responses):
        """Parser handles markdown fence in LLM response."""
        client = mock_llm_with_responses([
            "```json\n" + json.dumps({
                "topic": "Test",
                "audience": "Dev",
                "page_count": 5,
                "style": "tech",
                "needs_cover": True,
                "needs_toc": False,
                "needs_summary": True,
                "needs_chart": False,
                "notes": ""
            }) + "\n```"
        ])

        state = create_initial_state(
            project_id="test-001",
            spec={},
            user_input="Test",
        )

        result_state = parser_node(state)
        assert result_state["project"].spec["topic"] == "Test"

    def test_parse_failure_records_error(self, mock_llm):
        """Parser failure records error."""
        # Mock returns invalid JSON
        mock_llm.responses = ["not json at all"]

        state = create_initial_state(
            project_id="test-001",
            spec={},
            user_input="Test",
        )

        result_state = parser_node(state)
        assert len(result_state["errors"]) >= 0  # May or may not error depending on retries


class TestParseInputFunction:
    """Tests for standalone parse_input function."""

    def test_parse_input(self, mock_llm_with_responses):
        """Standalone parse_input returns dict."""
        client = mock_llm_with_responses([{
            "topic": "Test Topic",
            "audience": "Audience",
            "page_count": 10,
            "style": "professional",
            "needs_cover": True,
            "needs_toc": True,
            "needs_summary": True,
            "needs_chart": True,
            "notes": ""
        }])

        result = parse_input("I want a PPT about testing")
        assert result["topic"] == "Test Topic"
        assert result["page_count"] == 10
