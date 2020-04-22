import hashlib
import base58
from aiohttp import web
from indy_vdr import ledger

from .config.defaults import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT



REVOCATION_REGISTRY_ID_HEADER = "X-Revocation-Registry-ID"


async def index(request):

    # Get revocation registry id
    revocation_reg_id = request.headers.get(REVOCATION_REGISTRY_ID_HEADER)
    if not revocation_reg_id:
        web.Response(f"Missing header: {REVOCATION_REGISTRY_ID_HEADER}", status=400)

    # Hash File
    sha256 = hashlib.sha256()
    while True:
        chunk = await request.content.readany()
        if not chunk:
            break

        sha256.update(chunk)

    digest = sha256.hexdigest()
    b58_digest = base58.b58encode(digest)

    # Fetch revocation registry from ledger

    return web.Response()


def start(settings):
    app = web.Application()
    app["settings"] = settings

    # Add routes
    app.add_routes([web.post("/", index)])

    web.run_app(
        app,
        host=settings.get("host") or DEFAULT_WEB_HOST,
        port=settings.get("port") or DEFAULT_WEB_PORT,
    )
