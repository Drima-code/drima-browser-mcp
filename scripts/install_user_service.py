"""Install this checkout as a private per-user systemd service; no root required."""

import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
executable = root / ".venv/bin/drima-browser"
if not executable.is_file():
    raise SystemExit("Run uv sync --frozen first")
unit_dir = Path.home() / ".config/systemd/user"
unit_dir.mkdir(parents=True, exist_ok=True)
unit = unit_dir / "drima-browser.service"
unit.write_text(f"""[Unit]
Description=Drima local browser MCP
After=graphical-session.target

[Service]
Type=simple
WorkingDirectory={root}
ExecStart={executable} serve
Restart=on-failure
RestartSec=3
UMask=0077
TimeoutStopSec=15

[Install]
WantedBy=default.target
""")
env_names = [
    name
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR")
    if name in os.environ
]
if env_names:
    subprocess.run(
        ["systemctl", "--user", "import-environment", *env_names], check=True
    )
subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
subprocess.run(
    ["systemctl", "--user", "enable", "--now", "drima-browser.service"], check=True
)
print(f"Installed {unit}; browser opens lazily on first browser_open call.")
