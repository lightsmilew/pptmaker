"""Build installable Folio releases without copying the source checkout or .env."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd):
    print(f"Running: {' '.join(map(str, command))}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def certificate_pair(directory, domain=None):
    """Select a matching PEM certificate/key pair; never print key contents."""
    if not directory.is_dir():
        return None
    pairs = []
    for key in sorted(directory.rglob("*.key")):
        if key.is_symlink():
            raise ValueError("Certificate inputs must be regular files, not symbolic links")
        for extension in (".pem", ".crt", ".cer"):
            cert = key.with_suffix(extension)
            if cert.is_file() and not cert.is_symlink():
                pairs.append((cert, key))
                break
    if domain and len(pairs) > 1:
        pairs = [pair for pair in pairs if pair[1].stem == domain]
    if not pairs:
        if any(directory.rglob("*.key")):
            raise ValueError("No matching certificate found for the .key files in the certificate directory")
        return None
    if len(pairs) != 1:
        raise ValueError("Multiple certificate pairs found; select one with --domain")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(pairs[0][0]), str(pairs[0][1]), password=lambda: "")
    return pairs[0]


def valid_domain(value):
    value = value.lower()
    if len(value) > 253 or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value):
        raise ValueError("--domain must be a DNS hostname without scheme, port, path or wildcard")
    return value


def wheel_version(wheel):
    with zipfile.ZipFile(wheel) as archive:
        metadata_files = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_files) != 1:
            raise ValueError("Expected one distribution in the backend wheel")
        metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        if metadata["Name"] != "folio-studio":
            raise ValueError("Backend wheel is not folio-studio")
        return metadata["Version"]


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def prepare_payload(destination, wheel, frontend, domain, certificates, *, bundle_dependencies=False):
    """Only known release inputs enter the package, never repository-wide copies."""
    destination.mkdir()
    (destination / "backend").mkdir()
    shutil.copy2(wheel, destination / "backend" / wheel.name)
    for path in frontend.rglob("*"):
        if path.is_symlink() or (path.is_file() and
                (path.name.startswith(".env") or path.suffix.lower() in {".key", ".pem", ".crt", ".p12", ".pfx", ".db", ".sqlite3"})):
            raise ValueError("Unexpected secret/database input in the frontend build")
    shutil.copytree(frontend, destination / "frontend", ignore=shutil.ignore_patterns("*.map"))
    if not (destination / "frontend" / "index.html").is_file():
        raise ValueError("The frontend build is missing index.html")
    for source in sorted((ROOT / "deployment").rglob("*")):
        if source.is_file():
            text = source.read_text(encoding="utf-8").replace("@@DOMAIN@@", domain)
            write_text(destination / "deployment" / source.relative_to(ROOT / "deployment"), text)
    shutil.copy2(ROOT / "DEPLOY.md", destination / "DEPLOY.md")
    for relative in ("docs/OPERATIONS.md", "docs/images/production-admin-login.jpg", "docs/images/production-admin-mobile.jpg"):
        source = ROOT / relative
        if source.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    if certificates:
        cert, key = certificates
        (destination / "tls").mkdir(mode=0o700)
        shutil.copyfile(cert, destination / "tls" / f"{domain}.pem")
        private_key = destination / "tls" / f"{domain}.key"
        shutil.copyfile(key, private_key)
        private_key.chmod(0o600)
    if bundle_dependencies:
        if sys.platform != "linux":
            raise ValueError("--bundle-dependencies requires a Linux build host matching the deployment Python and CPU")
        run([sys.executable, "-m", "pip", "wheel", str(destination / "backend" / wheel.name),
             "--wheel-dir", str(destination / "wheelhouse")], ROOT)


def finalize_payload(destination, domain, version, contains_key):
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=False) if shutil.which("git") else None
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                            text=True, check=False) if commit and commit.returncode == 0 else None
    info = {
        "application": "Folio", "version": version, "domain": domain,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": commit.stdout.strip() if commit and commit.returncode == 0 else None,
        "git_dirty": bool(status.stdout.strip()) if status and status.returncode == 0 else None,
        "contains_tls_private_key": contains_key,
        "dependencies_bundled": (destination / "wheelhouse").is_dir(),
        "python_required": ">=3.10", "backend_workers": 1,
    }
    write_text(destination / "release.json", json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    files = sorted(path for path in destination.rglob("*") if path.is_file() and path != destination / "SHA256SUMS")
    write_text(destination / "SHA256SUMS", "".join(
        f"{digest(path)}  {path.relative_to(destination).as_posix()}\n" for path in files))


def archive_payload(directory, output):
    files = sorted(path for path in directory.rglob("*") if path.is_file())
    archive_zip = output / f"{directory.name}.zip"
    with zipfile.ZipFile(archive_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(directory)
            entry = zipfile.ZipInfo(f"{directory.name}/{relative.as_posix()}")
            entry.create_system = 3
            mode = 0o600 if path.suffix == ".key" else 0o755 if path.suffix == ".sh" else 0o644
            entry.external_attr = (0o100000 | mode) << 16
            archive.writestr(entry, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    archive_tar = output / f"{directory.name}.tar.gz"
    with tarfile.open(archive_tar, "w:gz") as archive:
        for path in files:
            entry = archive.gettarinfo(str(path), arcname=f"{directory.name}/{path.relative_to(directory).as_posix()}")
            entry.uid = entry.gid = 0
            entry.uname = entry.gname = ""
            entry.mode = 0o600 if path.suffix == ".key" else 0o755 if path.suffix == ".sh" else 0o644
            with path.open("rb") as stream:
                archive.addfile(entry, stream)
    for archive in (archive_zip, archive_tar):
        archive.chmod(0o600)
        write_text(output / f"{archive.name}.sha256", f"{digest(archive)}  {archive.name}\n")
    return archive_zip, archive_tar


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build Folio static frontend + backend wheel + deployment templates")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--domain", help="Defaults to the selected certificate filename, or folio.example.com")
    parser.add_argument("--cert-dir", type=Path, default=ROOT / "deploy")
    parser.add_argument("--without-certificates", action="store_true", help="Create a package suitable for sharing without TLS secrets")
    parser.add_argument("--skip-npm-ci", action="store_true", help="Reuse existing frontend dependencies")
    parser.add_argument("--bundle-dependencies", action="store_true", help="Include offline Python dependencies (matching Linux host only)")
    parser.add_argument("--release-name", help="Optional unique directory/archive name, e.g. folio-0.1.0-r1")
    args = parser.parse_args(argv)
    if args.release_name and not re.fullmatch(r"folio-[A-Za-z0-9][A-Za-z0-9._-]*", args.release_name):
        parser.error("--release-name must begin with folio- and contain only letters, numbers, dots, underscores or hyphens")
    if args.bundle_dependencies and sys.platform != "linux":
        parser.error("--bundle-dependencies requires a matching Linux build host")
    try:
        certificates = None if args.without_certificates else certificate_pair(args.cert_dir.resolve(), args.domain)
        domain = valid_domain(args.domain or (certificates[1].stem if certificates else "folio.example.com"))
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise ValueError("Node.js/npm is required on the build machine")
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=True)
        if args.release_name and any((output / (args.release_name + suffix)).exists()
                                     for suffix in ("", ".zip", ".tar.gz", ".zip.sha256", ".tar.gz.sha256")):
            raise ValueError("This release already exists; choose a new --release-name")
        with tempfile.TemporaryDirectory(prefix=".folio-build-", dir=output) as temporary:
            staging = Path(temporary)
            if not args.skip_npm_ci:
                run([npm, "ci"], ROOT / "frontend")
            run([npm, "run", "build"], ROOT / "frontend")
            # Build from an allowlist so setuptools cannot pick up old build artifacts,
            # uploads, .env, certificates or test fixtures.
            source = staging / "source"
            source.mkdir()
            shutil.copy2(ROOT / "backend" / "pyproject.toml", source / "pyproject.toml")
            shutil.copytree(ROOT / "backend" / "app", source / "app",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env*", "*.key", "*.pem", "*.crt", "*.p12", "*.pfx", "*.sqlite*", "*.db"))
            wheels = staging / "wheels"
            run([sys.executable, "-m", "pip", "wheel", str(source), "--no-deps", "--wheel-dir", str(wheels)], ROOT)
            wheel_files = list(wheels.glob("folio_studio-*.whl"))
            if len(wheel_files) != 1:
                raise ValueError("Expected exactly one Folio backend wheel")
            version = wheel_version(wheel_files[0])
            name = args.release_name or f"folio-{version}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
            payload = staging / name
            prepare_payload(payload, wheel_files[0], ROOT / "frontend" / "dist", domain, certificates,
                            bundle_dependencies=args.bundle_dependencies)
            finalize_payload(payload, domain, version, certificates is not None)
            artifacts = archive_payload(payload, staging)
            shutil.move(str(payload), output / name)
            for artifact in artifacts:
                shutil.move(str(artifact), output / artifact.name)
                checksum = staging / f"{artifact.name}.sha256"
                shutil.move(str(checksum), output / checksum.name)
        print(f"Release: {output / name}")
        print(f"Packages: {name}.zip / {name}.tar.gz")
        print(f"Domain: {domain}; TLS certificate/key bundled: {bool(certificates)}")
        if certificates:
            print("This package contains a TLS private key. Transfer privately; do not publish the archive.")
        return 0
    except (ValueError, OSError, ssl.SSLError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
