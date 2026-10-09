"""Development wrapper for the installed folio-manage-user command."""
import os
from pathlib import Path
import sys

backend = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend))
os.chdir(backend)

if __name__ == "__main__":
    from app.cli import manage_user
    manage_user()
