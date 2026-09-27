"""Real browsers against synthetic local content; never calls a job site."""

import asyncio

import pytest
from mcp import Client
from pydantic import ValidationError

from drima_browser.browser import Action, Browser, Target, log_url, public_url
from drima_browser.server import create_server

HTML = """<!doctype html><title>Local application test</title>
<form onsubmit="event.preventDefault();window.submissions=(window.submissions||0)+1;document.querySelector('#receipt').textContent='Received once'">
<label>Name <input id="name" name="name" required></label>
<label>Notes <textarea id="notes"></textarea></label>
<label>Language <select id="language"><option value="es">Spanish</option><option value="en">English</option></select></label>
<label><input type="checkbox" id="consent">Consent</label>
<label>CV <input id="cv" type="file"></label>
<button type="submit">Submit application</button><div id="receipt"></div></form>
<button onclick="confirm('Confirm example?')">Show dialog</button>
<button>Duplicate</button><button>Duplicate</button>
<iframe id="inside" srcdoc='<label>Inside<input id="inner"></label>'></iframe>
"""


@pytest.fixture(params=["firefox", "chromium"])
async def browser(tmp_path, request):
    browser = Browser(tmp_path, headless=True, engine=request.param)
    await browser.ensure()
    yield browser
    await browser.close()


async def form(browser):
    opened = await browser.open("about:blank")
    tab = opened["tab_id"]
    await browser.page(tab).set_content(HTML)
    return tab


async def test_real_form_fill_select_check_upload_and_receipt(browser, tmp_path):
    tab = await form(browser)
    result = await browser.act(
        tab,
        [
            Action(action="fill", target=Target(label="Name"), value="Alex Sample"),
            Action(
                action="fill", target=Target(label="Notes"), value="Line one\nLine two"
            ),
            Action(
                action="select",
                target=Target(role="combobox", name="Language"),
                value="en",
            ),
            Action(action="check", target=Target(label="Consent")),
        ],
        1000,
    )
    assert result["ok"]
    assert await browser.page(tab).evaluate("window.submissions||0") == 0
    assert await browser.page(tab).locator("#language").input_value() == "en"
    assert await browser.page(tab).locator("#consent").is_checked()
    upload = tmp_path / "cv.txt"
    upload.write_text("Synthetic CV")
    await browser.locator(tab, Target(label="CV")).set_input_files(str(upload))
    snapshot = await browser.snapshot(tab, 50)
    assert snapshot["truncated"]
    assert any(control.get("files") == ["cv.txt"] for control in snapshot["controls"])
    result = await browser.act(
        tab,
        [
            Action(
                action="click", target=Target(role="button", name="Submit application")
            )
        ],
        1000,
    )
    assert result["ok"]
    assert await browser.page(tab).locator("#receipt").inner_text() == "Received once"
    assert await browser.page(tab).evaluate("window.submissions") == 1


async def test_batch_stops_before_submission_after_failed_action(browser):
    tab = await form(browser)
    result = await browser.act(
        tab,
        [
            Action(action="fill", target=Target(label="Name"), value="Alex"),
            Action(action="click", target=Target(selector="#missing")),
            Action(
                action="click", target=Target(role="button", name="Submit application")
            ),
        ],
        100,
    )
    assert not result["ok"]
    assert result["completed"] == [0]
    assert result["failed_index"] == 1
    assert result["outcome"] == "unknown"
    assert await browser.page(tab).evaluate("window.submissions||0") == 0


async def test_duplicate_buttons_are_not_silently_selected(browser):
    tab = await form(browser)
    result = await browser.act(
        tab,
        [Action(action="click", target=Target(role="button", name="Duplicate"))],
        100,
    )
    assert not result["ok"]
    assert "Ambiguous" in result["error"]


async def test_stable_tabs_and_closed_tab_rejection(browser):
    first = await browser.open("about:blank")
    second = await browser.open("about:blank")
    await browser.page(first["tab_id"]).close()
    assert browser.page(second["tab_id"])
    with pytest.raises(ValueError, match="Unknown/closed"):
        browser.page(first["tab_id"])


async def test_iframe_form_target(browser):
    tab = await form(browser)
    result = await browser.act(
        tab,
        [
            Action(
                action="fill",
                target=Target(label="Inside", frame="#inside"),
                value="nested",
            )
        ],
        1000,
    )
    assert result["ok"]
    assert (
        await browser.page(tab).frame_locator("#inside").locator("#inner").input_value()
        == "nested"
    )


async def test_dialog_can_be_resolved_without_clicking_twice(browser):
    tab = await form(browser)
    click = asyncio.create_task(
        browser.page(tab).get_by_role("button", name="Show dialog").click()
    )
    for _ in range(100):
        if tab in browser.dialogs:
            break
        await asyncio.sleep(0.01)
    assert tab in browser.dialogs
    assert browser.dialogs[tab].message == "Confirm example?"
    await browser.dialogs.pop(tab).dismiss()
    await click


async def test_profile_persists_cookie_across_browser_restart(browser):
    await browser.context.add_cookies(
        [
            {
                "name": "synthetic_login",
                "value": "example",
                "domain": "example.test",
                "path": "/",
                "expires": 2000000000,
            }
        ]
    )
    await browser.close()
    await browser.ensure()
    cookies = await browser.context.cookies()
    assert any(cookie["name"] == "synthetic_login" for cookie in cookies)


async def test_mcp_discovers_tools_uploads_and_returns_real_image(tmp_path):
    browser = Browser(tmp_path, headless=True)
    server = create_server(browser)
    async with Client(server) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        assert {
            "browser_open",
            "browser_snapshot",
            "browser_upload",
            "browser_screenshot",
            "browser_act",
        } <= names
        opened = await client.call_tool("browser_open", {"url": "about:blank"})
        assert not opened.is_error
        tab = opened.structured_content["tab_id"]
        await browser.page(tab).set_content(HTML)
        file = tmp_path / "sample.txt"
        file.write_text("Synthetic")
        uploaded = await client.call_tool(
            "browser_upload",
            {"tab_id": tab, "target": {"label": "CV"}, "paths": [str(file)]},
        )
        assert not uploaded.is_error
        assert (
            await browser.page(tab).locator("#cv").evaluate("e => e.files[0].name")
            == "sample.txt"
        )
        screenshot = await client.call_tool("browser_screenshot", {"tab_id": tab})
        assert not screenshot.is_error
        assert screenshot.content[0].type == "image"
        assert len(screenshot.content[0].data) > 1000


def test_navigation_and_target_validation():
    for url in (
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://user:pass@example.test",
    ):
        with pytest.raises(ValueError):
            public_url(url)
    assert public_url("http://localhost:8000/form")
    with pytest.raises(ValidationError):
        Target(selector="#a", label="b")
    assert (
        log_url("https://example.test/form?token=secret#private")
        == "https://example.test/form"
    )


async def test_download_saved_outside_repo_with_unique_name(browser):
    tab = await form(browser)
    page = browser.page(tab)
    async with page.expect_download():
        await page.evaluate("""() => {
          const a = document.createElement('a');
          a.href = URL.createObjectURL(new Blob(['synthetic download']));
          a.download = 'receipt.txt'; document.body.append(a); a.click();
        }""")
    await asyncio.gather(*browser.tasks)
    saved = next(iter(browser.downloads.values()))
    assert saved["status"] == "complete"
    from pathlib import Path

    assert Path(saved["path"]).read_text() == "synthetic download"
    assert Path(saved["path"]).parent == browser.data_dir / "downloads"
