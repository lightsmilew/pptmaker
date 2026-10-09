#!/usr/bin/env bash
# Install this release's wheel into its own venv; no source checkout.
set -euo pipefail
release_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$release_dir"
sha256sum --check SHA256SUMS
if [[ -e .venv ]]; then
    echo "A venv already exists. Install into a fresh release directory." >&2
    exit 1
fi
set -- "$release_dir"/backend/folio_studio-*.whl
if [[ $# -ne 1 || ! -f "$1" ]]; then
    echo "Expected exactly one Folio backend wheel." >&2
    exit 1
fi
python3 -m venv "$release_dir/.venv"
if [[ -d "$release_dir/wheelhouse" ]]; then
    "$release_dir/.venv/bin/python" -m pip install --no-index --find-links "$release_dir/wheelhouse" "$1"
else
    "$release_dir/.venv/bin/python" -m pip install "$1"
fi
"$release_dir/.venv/bin/python" -m pip check
"$release_dir/.venv/bin/folio-server" --help
echo "Installed. Configure /etc/folio, Nginx and systemd using DEPLOY.md."
