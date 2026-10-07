"""Register the opt-in native host. Does not install/enable any Firefox extension."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
executable = root / ".venv/bin/drima-browser-native"
if not executable.is_file():
    raise SystemExit("Run uv sync --frozen first")
directory = Path.home() / ".mozilla/native-messaging-hosts"
directory.mkdir(parents=True, exist_ok=True)
manifest = directory / "drima_regular_browser.json"
if manifest.exists():
    raise SystemExit(f"Already registered at {manifest}; inspect before replacing")
manifest.write_text(
    json.dumps(
        {
            "name": "drima_regular_browser",
            "description": "Drima user-approved Firefox tabs",
            "path": str(executable),
            "type": "stdio",
            "allowed_extensions": ["approved-tabs@drima-browser.local"],
        },
        indent=2,
    )
    + "\n"
)
manifest.chmod(0o600)
print(f"Registered native host at {manifest}")
print(
    f"In normal Firefox, open about:debugging#/runtime/this-firefox, Load Temporary Add-on, select {root / 'extension/manifest.json'}"
)
print(
    "Open the connector toolbar popup: approve a website tab manually, or explicitly opt in to automatic website access."
)
