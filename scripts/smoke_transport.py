"""Exercise authenticated HTTP and stdio proxy against a temporary local service."""

import asyncio
import json
import socket
import subprocess
import tempfile
import time
from argparse import Namespace
from pathlib import Path

from mcp import Client, StdioServerParameters

from drima_browser.cli import connected


async def exercise(args, executable):
    opened = await connected(
        args, lambda client: client.call_tool("browser_open", {"url": "about:blank"})
    )
    assert not opened.is_error, opened
    payload = opened.structured_content or json.loads(opened.content[0].text)
    tab = payload["tab_id"]
    parameters = StdioServerParameters(
        command=str(executable),
        args=["--port", str(args.port), "--data-dir", str(args.data_dir), "stdio"],
    )
    for _ in range(2):
        async with Client(parameters) as client:
            tools = await client.list_tools()
            assert len(tools.tools) >= 14
            status = await client.call_tool("browser_status", {})
            result = status.structured_content or json.loads(status.content[0].text)
            assert any(page["tab_id"] == tab for page in result["tabs"])
            shot = await client.call_tool("browser_screenshot", {"tab_id": tab})
            assert not shot.is_error
            assert shot.content[0].type == "image"
    print(
        "PASS: authenticated HTTP, stdio discovery, image forwarding, browser survives two client reconnects"
    )


def main():
    executable = Path(__file__).resolve().parents[1] / ".venv/bin/drima-browser"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="drima-transport-") as directory:
        args = Namespace(port=port, data_dir=Path(directory))
        log_path = Path(directory) / "server.log"
        with log_path.open("w") as log:
            process = subprocess.Popen(
                [
                    str(executable),
                    "--port",
                    str(port),
                    "--data-dir",
                    directory,
                    "serve",
                    "--headless",
                ],
                stdout=log,
                stderr=log,
            )
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            break
                    except OSError:
                        if process.poll() is not None:
                            raise RuntimeError(log_path.read_text())
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Test service failed to start")
                asyncio.run(exercise(args, executable))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
