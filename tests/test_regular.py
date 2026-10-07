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
    assert set(manifest["permissions"]) == {"activeTab", "nativeMessaging", "storage"}
    assert set(manifest["optional_permissions"]) == {"http://*/*", "https://*/*"}
    harness = r"""
const vm=require('vm'), fs=require('fs'), assert=require('assert');
const events={}, messages=[];
let listener, granted=false, active=1, settings={};
const tabs=new Map([[1,{id:1,title:'Job',url:'https://wellfound.com/jobs/1?private=omit'}],
 [2,{id:2,title:'Other',url:'https://example.com/'}],
 [3,{id:3,title:'Private',url:'https://private.example/',incognito:true}],
 [4,{id:4,title:'Internal',url:'about:config'}]]);
const event=name=>({addListener:fn=>events[name]=fn});
const port={onMessage:{addListener:fn=>listener=fn},onDisconnect:event('disconnect'),postMessage:m=>messages.push(m)};
const browser={tabs:{get:async id=>tabs.get(id),executeScript:async()=>{},sendMessage:async()=>({ok:true}),
 query:async q=>q.active?[tabs.get(active)]:Array.from(tabs.values()),
 onRemoved:event('removed'),onUpdated:event('updated')},
 runtime:{id:'bridge',getURL:p=>'moz-extension://bridge/'+p,connectNative:()=>port,onMessage:event('ui')},
 permissions:{contains:async()=>granted,onRemoved:event('permissionRemoved')},
 storage:{local:{get:async()=>settings,set:async s=>{settings={...settings,...s}}}},
 browserAction:{setBadgeText:async()=>{}}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{browser,URL,Map,Set});
const sender={id:'bridge',url:'moz-extension://bridge/popup.html'};
const ui=r=>events.ui(r,sender);
(async()=>{
 assert.equal((await ui({ui:'state'})).mode,'manual');
 await assert.rejects(()=>ui({ui:'all',confirmed:true}),/permission/);
 await assert.rejects(()=>events.ui({ui:'all',confirmed:true},{id:'bridge',url:'https://evil.example'}),/popup/);
 await ui({ui:'toggle',tabId:1});
 await listener({id:'list',op:'tabs'});
 assert.equal(messages.at(-1).result.tabs.length,1);
 assert.equal(messages.at(-1).result.tabs[0].url,'https://wellfound.com/jobs/1');
 await listener({id:'blocked',op:'snapshot',tab_id:'2'});
 assert(messages.at(-1).error.includes('not approved'));
 tabs.get(1).url='https://accounts.google.com/login';
 events.updated(1,{url:tabs.get(1).url});
 await listener({id:'revoked',op:'snapshot',tab_id:'1'});
 assert(messages.at(-1).error.includes('not approved'));
 // Any HTTP/HTTPS website can be manually approved, not just job sites.
 active=2;
 await ui({ui:'toggle',tabId:2});
 await listener({id:'other',op:'snapshot',tab_id:'2'});
 assert(messages.at(-1).result.ok);
 granted=true;
 await ui({ui:'all',confirmed:true});
 await listener({id:'all',op:'tabs'});
 assert.equal(messages.at(-1).result.mode,'all');
 assert.equal(messages.at(-1).result.tabs.length,2);
 tabs.set(5,{id:5,title:'Future',url:'http://future.example/'});
 await listener({id:'future',op:'snapshot',tab_id:'5'});
 assert(messages.at(-1).result.ok);
 await listener({id:'private',op:'snapshot',tab_id:'3'});
 assert(messages.at(-1).error.includes('not approved'));
 await listener({id:'internal',op:'snapshot',tab_id:'4'});
 assert(messages.at(-1).error.includes('not approved'));
 // Native clients cannot change modes.
 await listener({id:'bad-mode',op:'all',tab_id:'1'});
 assert(messages.at(-1).error.includes('Unsupported'));
 // Revocation is checked before every operation, even before event delivery.
 granted=false;
 await listener({id:'revoked-grant',op:'snapshot',tab_id:'2'});
 assert(messages.at(-1).error.includes('not approved'));
 await events.permissionRemoved();
 assert.equal((await ui({ui:'state'})).mode,'manual');
 granted=true;
 await ui({ui:'all',confirmed:true});
 await ui({ui:'manual'});
 await listener({id:'stopped',op:'tabs'});
 assert.equal(messages.at(-1).result.tabs.length,0);
 // Restart restores opt-in only if host permissions still exist.
 settings={mode:'all'};
 vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{browser,URL,Map,Set});
 assert.equal((await ui({ui:'state'})).mode,'all');
 granted=false;
 vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{browser,URL,Map,Set});
 assert.equal((await ui({ui:'state'})).mode,'manual');
})().catch(e=>{console.error(e);process.exit(1)});
"""
    result = subprocess.run(
        ["node", "-e", harness, str(root / "extension/background.js")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


async def test_popup_explicit_consent_denial_and_stop():
    extension = Path(__file__).resolve().parents[1] / "extension"
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        page = await browser.new_page()
        await page.set_content((extension / "popup.html").read_text())
        await page.evaluate("""() => {
          window.requests=[]; window.grant=false;
          window.state={mode:'manual',eligible:true,approved:false,tabId:7};
          window.browser={runtime:{sendMessage:async r=>{
            requests.push(r.ui);
            if(r.ui==='all')state.mode='all';
            if(r.ui==='manual')state.mode='manual';
            return state;
          }}, permissions:{request:async()=>{requests.push('permission');return grant},
            remove:async()=>{requests.push('remove');return true}}};
        }""")
        await page.evaluate((extension / "popup.js").read_text())
        assert await page.locator("#all").is_disabled()
        await page.locator("#consent").check()
        await page.locator("#all").click()
        await page.wait_for_function("document.querySelector('#error').textContent.includes('denied')")
        assert "all" not in await page.evaluate("requests")
        await page.evaluate("grant=true;requests=[]")
        await page.locator("#all").click()
        await page.wait_for_function("state.mode==='all'")
        assert (await page.evaluate("requests"))[:2] == ["permission", "all"]
        await page.locator("#manual").click()
        await page.wait_for_function("state.mode==='manual' && requests.includes('remove')")
        assert not await page.locator("#consent").is_checked()
        assert await page.locator("#all").is_disabled()
        await browser.close()
