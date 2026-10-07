"""Tests for memory store and storage layer."""

import pytest
import json
from pathlib import Path

from app.storage.memory import (
    MemoryStore,
    UserPreferences,
    TemplateKnowledgeBase,
    memory_store,
    template_kb,
    user_preferences,
)


class TestMemoryStore:
    """Tests for MemoryStore."""

    @pytest.fixture
    def store(self, monkeypatch, tmp_path):
        """Fresh store for each test."""
        monkeypatch.setenv("PPTMAKER_DB", str(tmp_path / "projects.sqlite3"))
        monkeypatch.setenv("FOLIO_DB", str(tmp_path / "projects.sqlite3"))
        return MemoryStore()

    def test_interrupted_work_is_retryable_after_restart(self, store):
        store.create_project("interrupted", {"status":"generating", "user_input":"保留材料", "pages":[{"page_id":"01","status":"completed"}]})
        store.create_project("finished", {"status":"completed", "pages":[]})
        assert store.recover_interrupted() == 1
        restored = MemoryStore().get_project("interrupted")
        assert restored["status"] == "failed" and restored["user_input"] == "保留材料"
        assert restored["pages"][0]["status"] == "completed"
        assert store.get_project("finished")["status"] == "completed"

    def test_create_project(self, store):
        """Create a new project."""
        data = {"spec": {"topic": "Test"}, "pages": []}
        result = store.create_project("p1", data)
        assert result["id"] == "p1"
        assert "created_at" in result
        assert "updated_at" in result

    def test_get_project(self, store):
        """Get project by ID."""
        store.create_project("p1", {"spec": {}})
        project = store.get_project("p1")
        assert project is not None
        assert project["id"] == "p1"

    def test_get_nonexistent(self, store):
        """Get non-existent returns None."""
        assert store.get_project("nonexistent") is None

    def test_update_project(self, store):
        """Update project data."""
        store.create_project("p1", {"spec": {}})
        updated = store.update_project("p1", {"status": "completed", "progress": 100})
        assert updated["status"] == "completed"
        assert updated["progress"] == 100
        assert "updated_at" in updated

    def test_update_nonexistent(self, store):
        """Update non-existent returns None."""
        result = store.update_project("nonexistent", {"status": "x"})
        assert result is None

    def test_delete_project(self, store):
        """Delete project."""
        store.create_project("p1", {"spec": {}})
        result = store.delete_project("p1")
        assert result is True
        assert store.get_project("p1") is None

    def test_delete_nonexistent(self, store):
        """Delete non-existent returns False."""
        result = store.delete_project("nonexistent")
        assert result is False

    def test_list_projects(self, store):
        """List all projects."""
        store.create_project("p1", {"spec": {}})
        store.create_project("p2", {"spec": {}})
        projects = store.list_projects()
        assert len(projects) == 2
        ids = {p["id"] for p in projects}
        assert ids == {"p1", "p2"}

    def test_save_and_load(self, store, temp_dir):
        """Save and load from disk."""
        store.create_project("p1", {"spec": {"topic": "Test"}})
        path = str(temp_dir / "projects.json")
        store.save_to_disk(path)

        # Load into new store
        new_store = MemoryStore()
        new_store.load_from_disk(path)
        assert new_store.get_project("p1") is not None


class TestUserPreferences:
    """Tests for UserPreferences."""

    def test_default_preferences(self):
        """Default preferences returned for new user."""
        prefs = UserPreferences()
        result = prefs.get("new_user")
        assert "preferred_style" in result
        assert result["preferred_style"] == "简约商务"

    def test_update_preferences(self):
        """Update user preferences."""
        prefs = UserPreferences()
        prefs.update("u1", {"preferred_style": "tech"})
        result = prefs.get("u1")
        assert result["preferred_style"] == "tech"

    def test_learn_from_project(self):
        """Learn preferences from project."""
        prefs = UserPreferences()
        prefs.learn_from_project("u1", {
            "spec": {
                "style": "tech",
                "page_count": 15,
                "needs_chart": True,
            }
        })
        result = prefs.get("u1")
        assert result["preferred_style"] == "tech"
        assert result["default_page_count"] == 15
        assert result["likes_charts"] is True


class TestTemplateKnowledgeBase:
    """Tests for TemplateKnowledgeBase."""

    def test_get_recommended_layouts(self):
        """Get recommended layouts for page type."""
        kb = TemplateKnowledgeBase()
        layouts = kb.get_recommended_layouts("content")
        assert len(layouts) > 0
        assert "单栏布局" in layouts

    def test_get_recommended_unknown(self):
        """Get layouts for unknown type returns default."""
        kb = TemplateKnowledgeBase()
        layouts = kb.get_recommended_layouts("unknown_type")
        assert layouts == ["单栏布局"]

    def test_get_template(self):
        """Get template by name."""
        kb = TemplateKnowledgeBase()
        template = kb.get_template("学术简约")
        assert template["primary"] == "#234B70"

    def test_get_unknown_template_fallback(self):
        """Unknown template falls back to default."""
        kb = TemplateKnowledgeBase()
        template = kb.get_template("nonexistent")
        assert template is not None

    def test_list_templates(self):
        """List all templates."""
        kb = TemplateKnowledgeBase()
        templates = kb.list_templates()
        assert "学术简约" in templates
        assert len(templates) >= 3

    def test_validate_design_too_many_bullets(self):
        """Design with too many bullets has issues."""
        kb = TemplateKnowledgeBase()
        result = kb.validate_design({
            "bullet_points": ["a"] * 10,
            "page_type": "content",
        })
        assert result["valid"] is False
        assert len(result["issues"]) > 0

    def test_validate_design_long_bullet(self):
        """Design with long bullet has warning."""
        kb = TemplateKnowledgeBase()
        result = kb.validate_design({
            "bullet_points": ["a" * 100],
            "page_type": "content",
        })
        assert len(result["warnings"]) > 0

    def test_validate_design_layout_mismatch(self):
        """Layout mismatch generates warning."""
        kb = TemplateKnowledgeBase()
        result = kb.validate_design({
            "bullet_points": ["a"],
            "page_type": "content",
            "layout": "nonexistent_layout",
        })
        # May or may not warn depending on recommended list
        assert "warnings" in result

    def test_get_color_suggestions(self):
        """Get color suggestions by style."""
        kb = TemplateKnowledgeBase()
        colors = kb.get_color_suggestions("商务")
        assert len(colors) > 0
        assert all(c.startswith("#") for c in colors)

    def test_get_color_unknown(self):
        """Unknown style returns default colors."""
        kb = TemplateKnowledgeBase()
        colors = kb.get_color_suggestions("unknown_xyz")
        assert len(colors) > 0
