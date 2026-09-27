import httpx2
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from drima_browser.server import LocalAuth


async def test_missing_wrong_token_and_browser_origin_are_rejected():
    async def endpoint(request):
        return JSONResponse({"ok": True})

    app = LocalAuth(Starlette(routes=[Route("/", endpoint)]), "synthetic-token")
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        assert (await client.get("/")).status_code == 403
        assert (
            await client.get("/", headers={"Authorization": "Bearer wrong"})
        ).status_code == 403
        assert (
            await client.get(
                "/",
                headers={
                    "Authorization": "Bearer synthetic-token",
                    "Origin": "https://evil.test",
                },
            )
        ).status_code == 403
        response = await client.get(
            "/", headers={"Authorization": "Bearer synthetic-token"}
        )
        assert response.status_code == 200
