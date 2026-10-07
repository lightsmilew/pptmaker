"""Memory and storage management."""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from .sqlite_repository import ProjectRepository


class MemoryStore:
    """In-memory store for active projects."""

    def __init__(self):
        self._projects: Dict[str, Dict[str, Any]] = {}
        self._repository = ProjectRepository()
        self._projects.update(self._repository.load_all())

    def _persist(self, project_id: str):
        item = self._projects[project_id]
        self._repository.save(project_id, item)

    def create_project(self, project_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new project."""
        data["id"] = project_id
        data["created_at"] = datetime.now().isoformat()
        data["updated_at"] = datetime.now().isoformat()
        self._projects[project_id] = data
        self._persist(project_id)
        return data

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project by ID."""
        return self._projects.get(project_id)

    def update_project(self, project_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update project data."""
        if project_id in self._projects:
            self._projects[project_id].update(data)
            self._projects[project_id]["updated_at"] = datetime.now().isoformat()
            self._persist(project_id)
            return self._projects[project_id]
        return None

    def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        if project_id in self._projects:
            del self._projects[project_id]
            self._repository.delete(project_id)
            return True
        return False

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects."""
        return list(self._projects.values())

    def recover_interrupted(self) -> int:
        """Persist a retryable state for workflows lost when the process exited."""
        interrupted = [p for p in self._projects.values() if p.get("status") in
                       {"parsing", "planning", "generating", "reviewing", "rendering"}]
        for project in interrupted:
            self.update_project(project["id"], {"status": "failed", "current_step": "上次制作已中断",
                "error": "服务重启中断了上次制作。材料与已生成页面已保留，可点击重新制作。"})
        return len(interrupted)

    def save_to_disk(self, path: str) -> None:
        """Save all projects to disk."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._projects, f, ensure_ascii=False, indent=2)

    def load_from_disk(self, path: str) -> None:
        """Load projects from disk."""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self._projects = json.load(f)


class UserPreferences:
    """Store user preferences and habits."""

    def __init__(self):
        self._preferences: Dict[str, Dict[str, Any]] = {}

    def get(self, user_id: str) -> Dict[str, Any]:
        """Get preferences for a user."""
        defaults = {
            "preferred_style": "简约商务",
            "default_page_count": 8,
            "likes_charts": True,
            "likes_images": True,
            "font_size": "medium",
            "dark_mode": True,
        }
        return self._preferences.get(user_id, defaults)

    def update(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """Update user preferences."""
        if user_id not in self._preferences:
            self._preferences[user_id] = {}
        self._preferences[user_id].update(preferences)

    def learn_from_project(self, user_id: str, project_data: Dict[str, Any]) -> None:
        """Learn user preferences from a completed project."""
        prefs = self._preferences.get(user_id, {})

        # Extract preferences from project
        spec = project_data.get("spec", {})
        if spec:
            prefs["preferred_style"] = spec.get("style", prefs.get("preferred_style"))
            prefs["default_page_count"] = spec.get("page_count", prefs.get("default_page_count"))
            prefs["likes_charts"] = spec.get("needs_chart", prefs.get("likes_charts"))

        self._preferences[user_id] = prefs


class TemplateKnowledgeBase:
    """Knowledge base for PPT templates and design rules."""

    # Layout recommendations by page type
    LAYOUT_MAP = {
        "cover": ["封面布局", "全图背景"],
        "toc": ["目录布局", "单栏布局"],
        "content": ["单栏布局", "双栏布局", "大图+文字"],
        "chart": ["图表页"],
        "conclusion": ["总结布局", "单栏布局"],
        "reference": ["单栏布局"],
        "thankyou": ["封面布局"],
    }

    # Design rules
    DESIGN_RULES = {
        "max_bullets_per_page": 5,
        "max_chars_per_bullet": 50,
        "ideal_page_count": (6, 15),
        "min_font_size": 14,
        "recommended_image_ratio": (16, 9),
    }

    # Color psychology
    COLOR_GUIDANCE = {
        "商务": ["#1E40AF", "#3B82F6", "#60A5FA"],
        "科技": ["#6366F1", "#8B5CF6", "#06B6D4"],
        "教育": ["#059669", "#10B981", "#34D399"],
        "医疗": ["#0891B2", "#06B6D4", "#22D3EE"],
        "金融": ["#059669", "#10B981", "#34D399"],
    }

    TEMPLATES = {}

    def get_recommended_layouts(self, page_type: str) -> List[str]:
        """Get recommended layouts for a page type."""
        return self.LAYOUT_MAP.get(page_type, ["单栏布局"])

    def get_color_suggestions(self, style: str) -> List[str]:
        """Get color suggestions based on style category."""
        for key in self.COLOR_GUIDANCE:
            if key in style:
                return self.COLOR_GUIDANCE[key]
        return self.COLOR_GUIDANCE["商务"]

    def get_template(self, name: str) -> Dict[str, Any]:
        """Get template by name."""
        from ..tools.slide_scene import get_theme
        return get_theme(name)

    def list_templates(self) -> List[str]:
        """List all available template names."""
        from ..tools.slide_scene import PALETTES
        return list(PALETTES)

    def validate_design(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate design compliance."""
        issues = []
        warnings = []

        # Check bullet count
        bullet_count = len(page_data.get("bullet_points", []))
        if bullet_count > self.DESIGN_RULES["max_bullets_per_page"]:
            issues.append(f"要点过多({bullet_count}个)，建议控制在{self.DESIGN_RULES['max_bullets_per_page']}个以内")

        # Check bullet length
        for bullet in page_data.get("bullet_points", []):
            if len(bullet) > self.DESIGN_RULES["max_chars_per_bullet"]:
                warnings.append("部分要点过长，建议精简")

        # Check layout match
        page_type = page_data.get("page_type")
        layout = page_data.get("layout")
        if page_type and layout:
            recommended = self.get_recommended_layouts(page_type)
            if layout not in recommended:
                warnings.append(f"建议使用{recommended[0]}替代当前版式")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }


# Global instances
memory_store = MemoryStore()
template_kb = TemplateKnowledgeBase()
user_preferences = UserPreferences()
