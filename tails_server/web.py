import hashlib
import base58
from aiohttp import web

from .vdrproxy import VDRProxy

from .config.defaults import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT


REVOCATION_REGISTRY_ID_HEADER = "X-Revocation-Registry-ID"
EXPECTED_CONTENT_TYPE = "application/octet-stream"


async def index(request):
    # Check content-type for octet stream
    content_type_header = request.headers.get("Content-Type")
    if content_type_header != "EXPECTED_CONTENT_TYPE":
        raise web.HTTPBadRequest(
            text="Request must pass header 'Content-Type: octet-stream'"
        )

    # Get revocation registry id
    revocation_reg_id = request.headers.get(REVOCATION_REGISTRY_ID_HEADER)
    if not revocation_reg_id:
        raise web.HTTPBadRequest(
            text=f"Missing header: {REVOCATION_REGISTRY_ID_HEADER}"
        )

    # Hash File
    sha256 = hashlib.sha256()
    while True:
        chunk = await request.content.readany()
        if not chunk:
            break

        sha256.update(chunk)

    digest = sha256.digest()
    b58_digest = base58.b58encode(digest)

    # Lookup revocation registry
    revocation_registry_definition = await request.app[
        "vdr_proxy"
    ].get_revocation_registry_definition(revocation_reg_id)
    tails_hash = revocation_registry_definition["data"]["value"]["tailsHash"]

    if tails_hash != b58_digest:
        raise web.HTTPBadRequest(text="tailsHash does not match hash of file.")

    # Aquire lock for file

    # Write file to os

    # Fetch revocation registry from ledger

    return web.Response()


def start(settings):
    app = web.Application()
    app["settings"] = settings
    app["vdr_proxy"] = VDRProxy(settings["indy_vdr_proxy_url"])

    # Add routes
    app.add_routes([web.post("/", index)])

    web.run_app(
        app,
        host=settings.get("host") or DEFAULT_WEB_HOST,
        port=settings.get("port") or DEFAULT_WEB_PORT,
    )
