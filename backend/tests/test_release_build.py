"""Release boundaries, private key placement and failure preservation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile

import pytest

spec = importlib.util.spec_from_file_location("folio_release_builder", Path(__file__).resolve().parents[2] / "scripts" / "build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "deployment").mkdir()
    (root / "deployment" / "test.conf").write_text("server_name @@DOMAIN@@;\n")
    (root / "DEPLOY.md").write_text("deployment instructions")
    (root / "docs").mkdir()
    (root / "docs" / "OPERATIONS.md").write_text("deployment record without credentials")
    (root / "docs" / "private.env").write_text("SECRET=must-not-ship")
    (root / ".env").write_text("SECRET=must-not-ship")
    (root / "account.sqlite3").write_text("user data")
    frontend = root / "frontend" / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("<title>Folio</title>")
    (frontend / "ignore.map").write_text("source map")
    wheel = root / "folio_studio-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("folio_studio-0.1.0.dist-info/METADATA", "Name: folio-studio\nVersion: 0.1.0\n")
    cert, key = root / "sample.pem", root / "sample.key"
    cert.write_text("test-only certificate fixture")
    key.write_text("test-only private key fixture")
    monkeypatch.setattr(builder, "ROOT", root)
    return root, wheel, frontend, (cert, key)


def test_release_contains_only_payload_and_keeps_key_out_of_webroot(inputs, tmp_path):
    root, wheel, frontend, certs = inputs
    payload = tmp_path / "folio-fixture"
    builder.prepare_payload(payload, wheel, frontend, "example.test", certs)
    builder.finalize_payload(payload, "example.test", "0.1.0", True)
    assert not (payload / ".env").exists()
    assert not (payload / "account.sqlite3").exists()
    assert (payload / "docs" / "OPERATIONS.md").read_text() == "deployment record without credentials"
    assert not (payload / "docs" / "private.env").exists()
    assert not (payload / "frontend" / "ignore.map").exists()
    assert (payload / "deployment" / "test.conf").read_text() == "server_name example.test;\n"
    assert (payload / "tls" / "example.test.key").read_text() == "test-only private key fixture"
    assert not list((payload / "frontend").rglob("*.key"))
    info = json.loads((payload / "release.json").read_text())
    assert info["contains_tls_private_key"] is True
    builder.finalize_payload(payload, "example.test", "0.1.0", True)
    for line in (payload / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert builder.digest(payload / name) == expected
    archives = builder.archive_payload(payload, tmp_path)
    with zipfile.ZipFile(archives[0]) as archive:
        entry = archive.getinfo("folio-fixture/tls/example.test.key")
        assert (entry.external_attr >> 16) & 0o777 == 0o600
    with tarfile.open(archives[1]) as archive:
        assert archive.getmember("folio-fixture/tls/example.test.key").mode == 0o600


def test_shareable_release_excludes_tls(inputs, tmp_path):
    _, wheel, frontend, _ = inputs
    payload = tmp_path / "folio-public"
    builder.prepare_payload(payload, wheel, frontend, "example.test", None)
    builder.finalize_payload(payload, "example.test", "0.1.0", False)
    assert not (payload / "tls").exists()
    assert json.loads((payload / "release.json").read_text())["contains_tls_private_key"] is False


def test_frontend_secret_causes_build_failure(inputs, tmp_path):
    _, wheel, frontend, _ = inputs
    (frontend / "accidental.key").write_text("test-only secret")
    with pytest.raises(ValueError, match="secret/database"):
        builder.prepare_payload(tmp_path / "folio-invalid", wheel, frontend, "example.test", None)


def test_failed_build_preserves_previous_release(inputs, tmp_path, monkeypatch):
    output = tmp_path / "dist"
    old = output / "folio-old"
    old.mkdir(parents=True)
    (old / "keep.txt").write_text("previous release")
    monkeypatch.setattr(builder.shutil, "which", lambda _: "npm")
    def fail(*args):
        raise subprocess.CalledProcessError(1, "npm")
    monkeypatch.setattr(builder, "run", fail)
    assert builder.main(["--output-dir", str(output), "--domain", "example.test", "--without-certificates"]) == 1
    assert (old / "keep.txt").read_text() == "previous release"
    assert list(output.iterdir()) == [old]


@pytest.mark.parametrize("domain", ["https://example.test", "example.test;include secret;", "*.example.test"])
def test_domain_cannot_inject_nginx_configuration(domain):
    with pytest.raises(ValueError):
        builder.valid_domain(domain)
