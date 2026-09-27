"""Shared authenticated MCP service, stdio proxy, and a small diagnostic client."""

import argparse
import asyncio
import base64
import json
import os
import secrets
from pathlib import Path

import httpx2
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent

from drima_browser.browser import Browser
from drima_browser.server import LocalAuth, create_server


def data_dir() -> Path:
    return Path(
        os.environ.get("DRIMA_BROWSER_DATA", Path.home() / ".local/share/drima-browser")
    )


def token(directory: Path, create: bool = False) -> str:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / "client-token"
    if create and not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as file:
            file.write(secrets.token_urlsafe(32))
    return path.read_text().strip()


async def connected(args, callback):
    url = f"http://127.0.0.1:{args.port}/mcp"
    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token(args.data_dir)}"},
        timeout=60,
        trust_env=False,
    ) as client:
        async with streamable_http_client(url, http_client=client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await callback(session)


async def proxy(args):
    async def list_tools(_ctx, _params):
        return await connected(args, lambda session: session.list_tools())

    async def call_tool(_ctx, params):
        # Never retry a failed network call: an action might already have executed.
        try:
            return await connected(
                args,
                lambda session: session.call_tool(params.name, params.arguments or {}),
            )
        except Exception as exc:
            return CallToolResult(
                is_error=True,
                content=[
                    TextContent(
                        type="text",
                        text=f"Browser service call failed ({type(exc).__name__}). Outcome may be unknown. "
                        "Check service status and page/history before retrying any mutation.",
                    )
                ],
            )

    server = Server(
        "drima-browser-proxy",
        version="0.1.0",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


async def call(args):
    if args.tool == "list":
        result = await connected(args, lambda session: session.list_tools())
        print(result.model_dump_json(by_alias=True))
        return
    arguments = json.loads(args.arguments)
    result = await connected(
        args, lambda session: session.call_tool(args.tool, arguments)
    )
    output = result.model_dump(mode="json", by_alias=True)
    for item in output.get("content", []):
        if item.get("type") == "image":
            if args.image_output:
                path = Path(args.image_output)
                path.write_bytes(base64.b64decode(item.pop("data")))
                item["saved_path"] = str(path.resolve())
            else:
                item["data"] = "[image omitted; use --image-output PATH]"
    if output.get("structuredContent") is not None:
        output = {"isError": output["isError"], "result": output["structuredContent"]}
    print(json.dumps(output, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--data-dir", type=Path, default=data_dir())
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--headless", action="store_true")
    serve.add_argument("--browser", choices=["firefox", "chromium"], default="firefox")
    sub.add_parser("stdio")
    call_parser = sub.add_parser("call")
    call_parser.add_argument("tool")
    call_parser.add_argument("arguments", nargs="?", default="{}")
    call_parser.add_argument("--image-output")
    args = parser.parse_args()
    if args.command == "serve":
        browser = Browser(args.data_dir, args.headless, args.browser)
        server = create_server(browser)
        app = server.streamable_http_app(json_response=True, stateless_http=True)
        uvicorn.run(
            LocalAuth(app, token(args.data_dir, create=True)),
            host="127.0.0.1",
            port=args.port,
            access_log=False,
            log_level="warning",
        )
    elif args.command == "stdio":
        asyncio.run(proxy(args))
    else:
        asyncio.run(call(args))


if __name__ == "__main__":
    main()
