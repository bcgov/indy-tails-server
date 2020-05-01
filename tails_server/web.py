import logging
import hashlib
import base58
import os
from tempfile import NamedTemporaryFile

from aiohttp import web

from .ledger import get_rev_reg_def, GenesisDecodeError, BadGenesisError

from .config.defaults import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT

LOGGER = logging.getLogger(__name__)

REVOCATION_REGISTRY_ID_HEADER = "X-Revocation-Registry-ID"
EXPECTED_CONTENT_TYPE = "application/octet-stream"
CHUNK_SIZE = 1024

routes = web.RouteTableDef()


@routes.get("/{revocation_reg_id}")
async def get_file(request):
    revocation_reg_id = request.match_info["revocation_reg_id"]
    storage_path = request.app["settings"]["storage_path"]

    response = web.StreamResponse()
    response.enable_compression()
    response.enable_chunked_encoding()

    # Stream the response since the file could be big.
    try:
        with open(os.path.join(storage_path, revocation_reg_id), "rb") as tails_file:
            await response.prepare(request)
            while True:
                chunk = tails_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                await response.write(chunk)

    except FileNotFoundError:
        raise web.HTTPNotFound()

    await response.write_eof()


@routes.put("/{revocation_reg_id}")
async def put_file(request):
    storage_path = request.app["settings"]["storage_path"]

    # Check content-type for octet stream
    content_type_header = request.headers.get("Content-Type")
    if content_type_header != EXPECTED_CONTENT_TYPE:
        raise web.HTTPBadRequest(
            text="Request must pass header 'Content-Type: octet-stream'"
        )

    # Grab genesis transactions as base64
    b64_genesis = request.headers.get("X-Genesis-Transactions")
    if not b64_genesis:
        raise web.HTTPBadRequest(
            text="Request must pass X-Genesis-Transactions header "
            + "containing base64 encoded genesis transactions for ledger"
        )

    # Lookup revocation registry and get tailsHash
    revocation_reg_id = request.match_info["revocation_reg_id"]
    try:
        revocation_registry_definition = await get_rev_reg_def(
            b64_genesis, revocation_reg_id, storage_path
        )
    except GenesisDecodeError:
        raise web.HTTPBadRequest(
            text="X-Genesis-Transactions header contains malformed base64 encoding."
        )
    except BadGenesisError:
        raise web.HTTPBadRequest(
            text="Genesis transactions are not valid."
        )

    if not revocation_registry_definition:
        raise web.HTTPNotFound()

    tails_hash = revocation_registry_definition["value"]["tailsHash"]

    # Process the file in chunks so we don't explode on large files.
    # Construct hash and write file in chunks.
    sha256 = hashlib.sha256()
    try:
        # This should be atomic across networked filesystems:
        # https://linux.die.net/man/3/open
        # http://nfs.sourceforge.net/ (D10)
        # 'x' mode == O_EXCL | O_CREAT
        with NamedTemporaryFile("w+b") as tmp_file, open(
            os.path.join(storage_path, revocation_reg_id), "xb"
        ) as tails_file:
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

            # File integrity is good so write file to permanent location.
            tmp_file.seek(0)
            while True:
                chunk = tmp_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                tails_file.write(chunk)

    except FileExistsError:
        raise web.HTTPConflict(text="This tails file already exists.")

    return web.Response(text=tails_hash)


def start(settings):
    app = web.Application()
    app["settings"] = settings

    # Add routes
    app.add_routes(routes)

    web.run_app(
        app,
        host=settings.get("host") or DEFAULT_WEB_HOST,
        port=settings.get("port") or DEFAULT_WEB_PORT,
    )
