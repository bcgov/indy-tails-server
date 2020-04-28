import hashlib
import base58
import os
from time import sleep
from tempfile import TemporaryFile

from aiohttp import web

from .vdrproxy import VDRProxy

from .config.defaults import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT


REVOCATION_REGISTRY_ID_HEADER = "X-Revocation-Registry-ID"
EXPECTED_CONTENT_TYPE = "application/octet-stream"
CHUNK_SIZE = 1024


async def index(request):
    # Check content-type for octet stream
    content_type_header = request.headers.get("Content-Type")
    if content_type_header != EXPECTED_CONTENT_TYPE:
        raise web.HTTPBadRequest(
            text="Request must pass header 'Content-Type: octet-stream'"
        )

    # Get revocation registry id
    revocation_reg_id = request.headers.get(REVOCATION_REGISTRY_ID_HEADER)
    if not revocation_reg_id:
        raise web.HTTPBadRequest(
            text=f"Missing header: {REVOCATION_REGISTRY_ID_HEADER}"
        )

    # Lookup revocation registry and get tailsHash
    revocation_registry_definition = await request.app[
        "vdr_proxy"
    ].get_revocation_registry_definition(revocation_reg_id)
    tails_hash = revocation_registry_definition["data"]["value"]["tailsHash"]

    # Process the file in chunks so we don't explode on large files.
    # Construct hash and write file in chunks.
    sha256 = hashlib.sha256()
    with TemporaryFile("w+b") as tmp_file:
        while True:
            chunk = await request.content.readany()
            if not chunk:
                break
            sha256.update(chunk)
            tmp_file.write(chunk)

        # Check file integrity against tailHash on ledger
        digest = sha256.digest()
        b58_digest = base58.b58encode(digest).decode("utf-8")
        if tails_hash != b58_digest:
            raise web.HTTPBadRequest(text="tailsHash does not match hash of file.")

        # File integrity is good so write file to permanent location
        # This should be atomic across networked filesystems:
        # https://linux.die.net/man/3/open
        # http://nfs.sourceforge.net/ (D10)
        # 'x' mode == O_EXCL | os.O_CREAT
        tmp_file.seek(0)
        storage_path = request.app["settings"]["storage_path"]
        try:
            with open(os.path.join(storage_path, revocation_reg_id), "xb") as tails_file:
                while True:
                    chunk = tmp_file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    tails_file.write(chunk)
        except FileExistsError:
            raise web.HTTPConflict(text="This tails file already exists.")

    return web.Response()


def start(settings):
    app = web.Application()
    app["settings"] = settings
    app["vdr_proxy"] = VDRProxy(settings["indy_vdr_proxy_url"])

    # Add routes
    app.add_routes([web.put("/", index)])

    web.run_app(
        app,
        host=settings.get("host") or DEFAULT_WEB_HOST,
        port=settings.get("port") or DEFAULT_WEB_PORT,
    )
