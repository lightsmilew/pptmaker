"""Offline administration. No public endpoint may change membership or quotas."""
import argparse
import json
import sys
from pathlib import Path

backend = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend))
# Use the same env and cwd-relative storage rules as the backend service.
import os
os.chdir(backend)
from app.config import settings
from app.storage.auth_repository import AuthRepository

parser = argparse.ArgumentParser(description="Manage an existing Folio server account")
parser.add_argument("--email", required=True)
parser.add_argument("--tier", choices=["basic","plus"])
parser.add_argument("--expires-at", help="ISO timestamp; use 'none' to clear expiration")
parser.add_argument("--monthly-output-limit", type=int, help="0 = unlimited; omitted keeps current budget")
args = parser.parse_args()
if args.monthly_output_limit is not None and args.monthly_output_limit < 0:
    parser.error("The output limit must be nonnegative")
if args.expires_at and args.expires_at != "none":
    from datetime import datetime
    try: datetime.fromisoformat(args.expires_at.replace("Z", "+00:00"))
    except ValueError: parser.error("Invalid ISO expiration timestamp")
repo = AuthRepository()
with repo.connect() as db:
    row = db.execute("SELECT id,email,membership,output_limit FROM users WHERE email=?",(args.email.strip().casefold(),)).fetchone()
    if not row: parser.error("Account does not exist; register in Folio first")
    membership = json.loads(row["membership"])
    if args.tier: membership["tier"] = args.tier
    if args.expires_at: membership["expires_at"] = None if args.expires_at == "none" else args.expires_at
    limit = row["output_limit"] if args.monthly_output_limit is None else args.monthly_output_limit
    db.execute("UPDATE users SET membership=?,output_limit=? WHERE id=?",(json.dumps(membership),limit,row["id"]))
    print(json.dumps({"email":row["email"],"membership":membership,"monthly_output_limit":limit},ensure_ascii=False))
