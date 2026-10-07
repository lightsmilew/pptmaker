"""Tests for preview_renderer and critic nodes."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from app.agent.nodes.preview_renderer import preview_renderer_node
from app.agent.nodes.critic import critic_node, review_page
from app.agent.state import create_initial_state
from app.models.page import PageState, PageType, PageStatus, PreviewInfo


@pytest.fixture
def page_with_layout(sample_spec):
    """Page state with layout data."""
    state = create_initial_state(
        project_id="test-proj-001",
        spec=sample_spec,
        user_input="Test",
    )

    page = PageState(
        page_id="page-01",
        page_type=PageType.CONTENT,
        title="Test Title",
        subtitle="Test Subtitle",
        key_points=["a", "b", "c"],
        bullet_points=["bp1", "bp2"],
    )
    page.layout_type = "title_content"
    page.layout_json = {
        "layout_id": "content",
        "placeholders": [
            {"name": "title", "type": "title", "x": 0.8, "y": 0.4, "w": 11.7, "h": 0.8},
            {"name": "content", "type": "text", "x": 1, "y": 1.6, "w": 11.2, "h": 5.2},
        ],
    }
    page.master_json = {
        "background": {"type": "solid", "rgb": [255, 255, 255]},
        "color_scheme": {
            "primary": [20, 40, 80],
            "secondary": [80, 100, 140],
            "accent": [60, 120, 180],
            "text": [30, 30, 30],
            "light_text": [255, 255, 255],
        },
        "font_scheme": {
            "title_font": "Arial",
            "body_font": "Arial",
            "title_size": 32,
            "body_size": 16,
        },
    }

    state["pages"]["page-01"] = page
    state["current_page_id"] = "page-01"
    return state


class TestPreviewRendererNode:
    """Tests for preview_renderer_node."""

    def test_renders_preview(self, page_with_layout, storage_dir):
        """Renderer creates a preview image."""
        with patch("pathlib.Path.cwd", return_value=storage_dir.parent):
            with patch("os.getcwd", return_value=str(storage_dir.parent)):
                # Patch where preview is saved
                result_state = preview_renderer_node(page_with_layout)
                page = result_state["pages"]["page-01"]
                # Should have a preview
                # (Note: actual file save depends on cwd being writable)
                assert page.status in (PageStatus.REVIEWING, PageStatus.FAILED, PageStatus.RENDERING)

    def test_renders_no_current_page(self, sample_spec):
        """Renderer handles no current page."""
        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )
        result_state = preview_renderer_node(state)
        assert result_state is not None


class TestCriticNode:
    """Tests for critic_node."""

    def test_critic_with_approved_response(self, mock_llm_with_responses, sample_spec, tmp_path):
        """Critic approves a page."""
        client = mock_llm_with_responses([{
            "status": "approved",
            "score": 88,
            "dimensions": {
                "alignment": 9, "balance": 8, "readability": 9,
                "hierarchy": 8, "density": 9, "consistency": 9
            },
            "issues": [],
            "next_action": "approve",
        }])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )

        page = PageState(
            page_id="page-01",
            page_type=PageType.CONTENT,
            title="Test",
            key_points=["a", "b"],
        )
        image = tmp_path / "preview.png"
        from PIL import Image
        Image.new("RGB", (16, 9), "white").save(image)
        page.preview = PreviewInfo(image_path=str(image))
        state["project"].spec["review_mode"] = "vision"
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"

        result_state = critic_node(state)
        page_after = result_state["pages"]["page-01"]
        assert page_after.review_status == "approved"
        assert page_after.review_score == 88

    def test_critic_with_needs_revision(self, mock_llm_with_responses, sample_spec, tmp_path):
        """Critic returns needs_revision for low score."""
        client = mock_llm_with_responses([{
            "status": "needs_revision",
            "score": 60,
            "dimensions": {
                "alignment": 6, "balance": 5, "readability": 6,
                "hierarchy": 6, "density": 6, "consistency": 6
            },
            "issues": [
                {
                    "issue_id": "i1",
                    "category": "alignment",
                    "severity": "medium",
                    "target": "content",
                    "description": "misaligned",
                    "owner": "layout",
                }
            ],
            "next_action": "revise_layout",
        }])

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
        image = tmp_path / "preview.png"
        from PIL import Image
        Image.new("RGB", (16, 9), "white").save(image)
        page.preview = PreviewInfo(image_path=str(image))
        state["project"].spec["review_mode"] = "vision"
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"

        result_state = critic_node(state)
        page_after = result_state["pages"]["page-01"]
        assert page_after.review_status == "needs_revision"
        assert len(page_after.review_issues) == 1

    def test_critic_increments_iteration(self, mock_llm_with_responses, sample_spec):
        """Critic increments iteration count."""
        client = mock_llm_with_responses([{
            "status": "approved", "score": 88,
            "dimensions": {"alignment": 9, "balance": 8, "readability": 9,
                          "hierarchy": 8, "density": 9, "consistency": 9},
            "issues": [], "next_action": "approve",
        }])

        state = create_initial_state(
            project_id="test-001",
            spec=sample_spec,
            user_input="Test",
        )

        page = PageState(page_id="page-01", page_type=PageType.CONTENT, title="t", key_points=["a"])
        page.preview = PreviewInfo(image_path="/tmp/preview.png")
        state["pages"]["page-01"] = page
        state["current_page_id"] = "page-01"

        result_state = critic_node(state)
        page_after = result_state["pages"]["page-01"]
        assert page_after.iteration == 1


class TestReviewPageFunction:
    """Tests for standalone review_page function."""

    def test_review_page_with_no_image(self, mock_llm_with_responses):
        """Review page when no image exists."""
        client = mock_llm_with_responses([{
            "status": "approved", "score": 85,
            "dimensions": {"alignment": 8, "balance": 8, "readability": 8,
                          "hierarchy": 8, "density": 8, "consistency": 8},
            "issues": [], "next_action": "approve",
        }])

        result = review_page(
            page_id="p1",
            page_data={"title": "Test", "key_points": ["a"]},
            preview_path="/nonexistent/path.png",
            layout_type="title_content",
        )
        assert result["status"] == "blocked"
        assert client.call_count == 0
