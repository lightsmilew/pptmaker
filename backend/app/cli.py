"""Installed release entry points; load external configuration before app imports."""
import argparse
from datetime import datetime
import json
import os
import re
import secrets
import sqlite3
from pathlib import Path


def _environment(path, parser):
    if path:
        file = Path(path).expanduser().resolve()
        if not file.is_file():
            parser.error(f"Environment file does not exist: {file}")
        from dotenv import load_dotenv
        load_dotenv(file, override=False)
        os.environ["FOLIO_ENV_FILE"] = str(file)


def serve(argv=None):
    parser = argparse.ArgumentParser(description="Run the Folio API with one backend worker")
    parser.add_argument("--env-file", help="External configuration, e.g. /etc/folio/runtime/folio.env")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    _environment(args.env_file, parser)
    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, workers=1, reload=False,
                proxy_headers=True, forwarded_allow_ips="127.0.0.1")


def manage_user(argv=None):
    parser = argparse.ArgumentParser(description="Manage an existing Folio server account")
    parser.add_argument("--env-file", help="Use the same external configuration as folio-server")
    parser.add_argument("--email", required=True)
    parser.add_argument("--tier", choices=["basic", "plus", "pro", "studio"])
    parser.add_argument("--expires-at", help="ISO timestamp; use 'none' to clear expiration")
    parser.add_argument("--monthly-output-limit", type=int, help="0 = unlimited; omitted keeps the current budget")
    args = parser.parse_args(argv)
    if args.monthly_output_limit is not None and args.monthly_output_limit < 0:
        parser.error("The output limit must be nonnegative")
    if args.expires_at and args.expires_at != "none":
        try:
            datetime.fromisoformat(args.expires_at.replace("Z", "+00:00"))
        except ValueError:
            parser.error("Invalid ISO expiration timestamp")
    _environment(args.env_file, parser)
    from .config import settings  # noqa: F401 - retains development backend/.env loading
    from .storage.auth_repository import AuthRepository
    repo = AuthRepository()
    with repo.connect() as db:
        row = db.execute("SELECT id,email,membership,output_limit FROM users WHERE email=?",
                         (args.email.strip().casefold(),)).fetchone()
        if not row:
            parser.error("Account does not exist; register in Folio first")
        membership = json.loads(row["membership"])
        if args.tier:
            membership["tier"] = args.tier
        if args.expires_at:
            membership["expires_at"] = None if args.expires_at == "none" else args.expires_at
        limit = row["output_limit"] if args.monthly_output_limit is None else args.monthly_output_limit
        db.execute("UPDATE users SET membership=?,output_limit=? WHERE id=?",
                   (json.dumps(membership), limit, row["id"]))
        print(json.dumps({"email": row["email"], "membership": membership,
                          "monthly_output_limit": limit}, ensure_ascii=False))


def create_admin(argv=None):
    parser = argparse.ArgumentParser(description="Create a NEW dedicated Folio administrator; existing users are never promoted")
    parser.add_argument("--env-file")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Folio 管理员")
    parser.add_argument("--credentials-file", required=True, help="New private file receiving the generated password once")
    args = parser.parse_args(argv)
    email = args.email.strip().casefold()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        parser.error("Invalid email address")
    if not args.name.strip() or len(args.name) > 40:
        parser.error("Name must have 1–40 characters")
    _environment(args.env_file, parser)
    from .config import settings  # noqa: F401
    from .storage.auth_repository import AuthRepository
    from .storage.admin_repository import AdminRepository
    path = Path(args.credentials_file).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)
    try:
        # Exclusive creation prevents overwriting another account's credentials.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        parser.error("Credentials file already exists or cannot be created")
    try:
        if os.name == "nt":
            import subprocess
            principal = os.environ.get("USERDOMAIN", "")+"\\"+os.environ["USERNAME"]
            secured = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", principal+":F"], capture_output=True)
            if secured.returncode:
                raise OSError("Cannot restrict the credentials file to its owner")
        uid = AuthRepository().create_admin(email, password, args.name.strip())
    except sqlite3.IntegrityError:
        os.close(fd)
        path.unlink()
        parser.error("Email already exists; choose a new administrator address")
    except Exception:
        os.close(fd)
        path.unlink()
        raise
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"Folio administrator\nLogin: /#/admin/login\nEmail: {email}\nPassword: {password}\nChange this password after first login.\n")
    AdminRepository().record("admin", uid, "admin.created", uid)
    print(f"Created dedicated administrator {email}. Credentials: {path}")


if __name__ == "__main__":
    serve()
