"""Opt-in connector tested only against synthetic pages and local IPC."""

import asyncio
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from drima_browser import regular
from drima_browser.native_host import (
    ensure_private_directory,
    read_message,
    write_message,
)


def test_native_framing_and_bounds():
    stream = io.BytesIO()
    write_message(stream, {"id": "synthetic", "op": "tabs"})
    stream.seek(0)
    assert read_message(stream) == {"id": "synthetic", "op": "tabs"}
    with pytest.raises(EOFError):
        read_message(io.BytesIO(b"\x01"))
    with pytest.raises(ValueError):
        write_message(io.BytesIO(), {"text": "x" * 300000})


def test_directory_permissions(tmp_path):
    directory = tmp_path / "private"
    ensure_private_directory(directory)
    assert directory.stat().st_mode & 0o777 == 0o700
    directory.chmod(0o755)
    with pytest.raises(ValueError):
        ensure_private_directory(directory)


async def test_bridge_single_shot_and_errors(tmp_path, monkeypatch):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    path = directory / "bridge.sock"
    monkeypatch.setattr(regular, "socket_path", lambda: path)
    received = []

    async def fake_host(reader, writer):
        payload = json.loads(await reader.readline())
        received.append(payload)
        writer.write(
            json.dumps(
                {"error": "Synthetic unknown outcome"}
                if payload["op"] == "act"
                else {"result": {"tabs": []}}
            ).encode()
            + b"\n"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_unix_server(fake_host, path=str(path))
    os.chmod(path, 0o600)
    async with server:
        assert await regular.request({"op": "tabs"}) == {"tabs": []}
        with pytest.raises(RuntimeError, match="unknown outcome"):
            await regular.request({"op": "act"})
        assert len(received) == 2
        os.chmod(path, 0o666)
        with pytest.raises(RuntimeError, match="permissions"):
            await regular.request({"op": "tabs"})
        assert len(received) == 2


async def test_real_native_host_roundtrip(tmp_path, monkeypatch):
    directory = tmp_path / "native"
    directory.mkdir(mode=0o700)
    path = directory / "regular-browser.sock"
    monkeypatch.setattr(regular, "socket_path", lambda: path)
    process = subprocess.Popen(
        [sys.executable, "-m", "drima_browser.native_host"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "DRIMA_REGULAR_BROWSER_DATA": str(directory)},
    )
    try:
        for _ in range(100):
            if path.exists():
                break
            await asyncio.sleep(0.02)
        assert path.exists()
        task = asyncio.create_task(regular.request({"op": "tabs"}))
        outgoing = await asyncio.wait_for(
            asyncio.to_thread(read_message, process.stdout), 5
        )
        assert outgoing["op"] == "tabs"
        write_message(
            process.stdin, {"id": outgoing["id"], "result": {"tabs": [{"tab_id": "7"}]}}
        )
        assert await task == {"tabs": [{"tab_id": "7"}]}
    finally:
        process.stdin.close()
        await asyncio.to_thread(process.wait, 5)
    assert not path.exists()


async def test_content_controls_and_no_duplicate_submission():
    script = (Path(__file__).resolve().parents[1] / "extension/content.js").read_text()
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        page = await browser.new_page()
        await page.set_content("""<title>Synthetic connector test</title>
          <label>Name<input id="name"></label><input id="password" type="password" value="do-not-expose">
          <input id="token" type="hidden" value="private"><button id="send" onclick="window.sent=(window.sent||0)+1">Send</button>
          <button class="duplicate">Duplicate</button><button class="duplicate">Duplicate</button>""")
        await page.evaluate(
            "window.browser={runtime:{onMessage:{addListener:fn=>window.handler=fn}}}"
        )
        await page.evaluate(script)
        await page.evaluate(script)
        snapshot = await page.evaluate(
            "handler({drima:true,op:'snapshot',max_chars:8000})"
        )
        assert not any(c["id"] in ("password", "token") for c in snapshot["controls"])
        await page.evaluate(
            "handler({drima:true,op:'act',action:'fill',selector:'#name',value:'Alex Sample'})"
        )
        assert await page.locator("#name").input_value() == "Alex Sample"
        with pytest.raises(Exception, match="Sensitive"):
            await page.evaluate(
                "handler({drima:true,op:'act',action:'fill',selector:'#password',value:'x'})"
            )
        with pytest.raises(Exception, match="exactly one"):
            await page.evaluate(
                "handler({drima:true,op:'act',action:'click',selector:'.duplicate'})"
            )
        await page.evaluate(
            "handler({drima:true,op:'act',action:'click',selector:'#send'})"
        )
        assert await page.evaluate("window.sent") == 1
        await browser.close()


def test_background_permissions_and_origin_revocation():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "extension/manifest.json").read_text())
    assert set(manifest["permissions"]) == {"activeTab", "nativeMessaging"}
    harness = r"""
const vm=require('vm'), fs=require('fs'), assert=require('assert');
const events={}, messages=[];
let listener;
const tabs=new Map([[1,{id:1,title:'Job',url:'https://wellfound.com/jobs/1?private=omit'}],
 [2,{id:2,title:'Other',url:'https://example.com/'}]]);
const event=name=>({addListener:fn=>events[name]=fn});
const port={onMessage:{addListener:fn=>listener=fn},onDisconnect:event('disconnect'),postMessage:m=>messages.push(m)};
const browser={tabs:{get:async id=>tabs.get(id),executeScript:async()=>{},sendMessage:async()=>({ok:true}),
 onRemoved:event('removed'),onUpdated:event('updated')},runtime:{connectNative:()=>port},
 browserAction:{onClicked:event('clicked'),setBadgeText:async()=>{}}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{browser,URL,Map,Set});
(async()=>{
 await events.clicked(tabs.get(1));
 await listener({id:'list',op:'tabs'});
 assert.equal(messages.at(-1).result.tabs.length,1);
 assert.equal(messages.at(-1).result.tabs[0].url,'https://wellfound.com/jobs/1');
 await listener({id:'blocked',op:'snapshot',tab_id:'2'});
 assert(messages.at(-1).error.includes('not approved'));
 tabs.get(1).url='https://accounts.google.com/login';
 events.updated(1,{url:tabs.get(1).url});
 await listener({id:'revoked',op:'snapshot',tab_id:'1'});
 assert(messages.at(-1).error.includes('not approved'));
})().catch(e=>{console.error(e);process.exit(1)});
"""
    result = subprocess.run(
        ["node", "-e", harness, str(root / "extension/background.js")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
