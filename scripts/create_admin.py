"""Development wrapper for the installed folio-create-admin command."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.cli import create_admin

if __name__ == "__main__":
    create_admin()
