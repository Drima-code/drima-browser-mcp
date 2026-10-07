"""Package only explicit extension assets, never profiles or repository data."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
extension = root / "extension"
manifest = json.loads((extension / "manifest.json").read_text())
output = Path("/tmp") / f"mcp-browser-bridge-{manifest['version']}.zip"
assets = (
    "manifest.json", "background.js", "content.js", "popup.html", "popup.js", "popup.css"
)
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for name in assets:
        archive.write(extension / name, name)
print(output)
