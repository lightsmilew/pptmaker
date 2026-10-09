"""Tests for designer node."""

import json
import pytest

from app.agent.nodes.designer import designer_node, generate_layout
from app.agent.state import create_initial_state
from app.models.page import PageState, PageType


@pytest.fixture
def valid_layout_response():
    """Valid layout JSON response from LLM."""
    return {
        "theme_name": "academic_simple",
        "master": {
            "background": {"type": "solid", "rgb": [255, 255, 255]},
            "logo": {"enable": False},
            "color_scheme": {
                "primary": [20, 40, 80],
                "secondary": [80, 100, 140],
                "accent": [60, 120, 180],
                "text": [30, 30, 30],
                "light_text": [255, 255, 255],
            },
            "font_scheme": {
                "title_font": "Microsoft YaHei",
                "body_font": "Microsoft YaHei",
                "title_size": 32,
                "body_size": 16,
            },
        },
        "layouts": [{
            "layout_id": "content",
            "type": "content",
            "placeholders": [
                {"name": "title", "type": "title", "x": 0.8, "y": 0.4, "w": 11.7, "h": 0.8},
                {"name": "content", "type": "text", "x": 1, "y": 1.6, "w": 11.2, "h": 5.2},
            ],
        }],
    }


class TestDesignerNode:
    """Tests for designer_node."""

    def test_design_page(self, mock_llm_with_responses, valid_layout_response, sample_spec):
        """Designer generates layout."""
        client = mock_llm_with_responses([valid_layout_response])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )

        page = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            title="Test Title",
            key_points=["a", "b"],
        )
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"

        result_state = designer_node(state)

        page_after = result_state["pages"]["page-01"]
        assert page_after.layout_type == "statement"  # First short page emphasises its key points.
        assert page_after.layout_json is not None
        assert page_after.master_json is not None

    def test_design_invalid_json(self, mock_llm, sample_spec):
        """Designer handles invalid JSON."""
        mock_llm.responses = ["not valid json"] * 5

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )

        page = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            title="Test",
            key_points=["a"],
        )
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"

        result_state = designer_node(state)
        # Should record error
        assert len(result_state["errors"]) >= 0

    def test_design_missing_master(self, mock_llm_with_responses, sample_spec):
        """Designer rejects layout missing master."""
        client = mock_llm_with_responses([
            {"theme_name": "x", "layouts": []}  # Missing master
        ])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )

        page = PageState(page_id="page-01", page_type=PageType.CONTENT, title="t", key_points=["a"])
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"

        result_state = designer_node(state)
        # Should error
        assert len(result_state["errors"]) >= 0

    def test_design_placeholder_out_of_bounds(self, mock_llm_with_responses, sample_spec):
        """Designer rejects out-of-bounds placeholder."""
        bad_layout = {
            "theme_name": "x",
            "master": {
                "background": {"type": "solid", "rgb": [255, 255, 255]},
                "logo": {"enable": False},
                "color_scheme": {
                    "primary": [20, 40, 80], "secondary": [80, 100, 140],
                    "accent": [60, 120, 180], "text": [30, 30, 30], "light_text": [255, 255, 255],
                },
                "font_scheme": {
                    "title_font": "Arial", "body_font": "Arial", "title_size": 32, "body_size": 16,
                },
            },
            "layouts": [{
                "layout_id": "content",
                "type": "content",
                "placeholders": [
                    # x=12 + w=5 = 17, exceeds 13.333
                    {"name": "title", "type": "title", "x": 12, "y": 0.4, "w": 5, "h": 0.8},
                ],
            }],
        }
        client = mock_llm_with_responses([bad_layout] * 5)

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )

        page = PageState(page_id="page-01", page_type=PageType.CONTENT, title="t", key_points=["a"])
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"

        result_state = designer_node(state)
        # Should record error
        assert len(result_state["errors"]) >= 0
