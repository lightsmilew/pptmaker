"""SQLite persistence for project snapshots."""
import json
import os
import sqlite3
from typing import Any, Dict, List


class ProjectRepository:
    def __init__(self, path: str = "storage/pptmaker.sqlite3"):
        self.path = os.getenv("FOLIO_DB") or os.getenv("PPTMAKER_DB", path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL)")

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            return {pid: json.loads(data) for pid, data in db.execute("SELECT id, data FROM projects")}

    def save(self, project_id: str, data: Dict[str, Any]) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO projects(id,data,updated_at) VALUES (?,?,?)",
                       (project_id, json.dumps(data, ensure_ascii=False, default=str), data.get("updated_at", "")))

    def delete(self, project_id: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM projects WHERE id=?", (project_id,))
