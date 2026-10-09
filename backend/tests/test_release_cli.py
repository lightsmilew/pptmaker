"""Installed commands must use explicit configuration and isolated identities."""
import json
from unittest.mock import patch

import pytest

from app.cli import manage_user, serve


def test_server_loads_external_env_before_start_and_uses_one_worker(tmp_path, monkeypatch):
    monkeypatch.delenv("FOLIO_RELEASE_TEST", raising=False)
    monkeypatch.delenv("FOLIO_ENV_FILE", raising=False)
    file = tmp_path / "production.env"
    file.write_text("FOLIO_RELEASE_TEST=external\n", encoding="utf-8")
    with patch("uvicorn.run") as run:
        serve(["--env-file", str(file), "--port", "8100"])
    import os
    assert os.environ["FOLIO_RELEASE_TEST"] == "external"
    monkeypatch.delenv("FOLIO_RELEASE_TEST")
    assert run.call_args.kwargs == dict(host="127.0.0.1", port=8100, workers=1, reload=False,
                                       proxy_headers=True, forwarded_allow_ips="127.0.0.1")


def test_server_bad_env_or_port_does_not_start(tmp_path):
    for argv in (["--env-file", str(tmp_path / "missing.env")], ["--port", "0"]):
        with patch("uvicorn.run") as run, pytest.raises(SystemExit):
            serve(argv)
        run.assert_not_called()


def test_admin_updates_isolated_account_without_touching_password(tmp_path, monkeypatch, capsys):
    from app.storage.auth_repository import AuthRepository
    file = tmp_path / "account.sqlite3"
    monkeypatch.setenv("FOLIO_DB", str(file))
    repo = AuthRepository()
    uid = repo.register("release@example.test", "Test-password-123", "Release test")
    with repo.connect() as db:
        before = db.execute("SELECT password_hash FROM users WHERE id=?", (uid,)).fetchone()[0]
    manage_user(["--email", " RELEASE@EXAMPLE.TEST ", "--tier", "plus", "--monthly-output-limit", "25000"])
    result = json.loads(capsys.readouterr().out)
    assert result["membership"]["tier"] == "plus"
    assert result["monthly_output_limit"] == 25000
    with repo.connect() as db:
        after = db.execute("SELECT password_hash FROM users WHERE id=?", (uid,)).fetchone()[0]
    assert after == before


@pytest.mark.parametrize("extra", [["--monthly-output-limit", "-1"], ["--expires-at", "not-a-date"]])
def test_admin_rejects_invalid_changes_before_database_access(extra):
    with patch("app.storage.auth_repository.AuthRepository") as repository, pytest.raises(SystemExit):
        manage_user(["--email", "release@example.test", *extra])
    repository.assert_not_called()
