import logging
import hashlib
import base58
import os

from os.path import isfile, join
from tempfile import NamedTemporaryFile

from aiohttp import web

from .config.defaults import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT, CHUNK_SIZE
from .ledger import (
    get_rev_reg_def,
    BadGenesisError,
    BadRevocationRegistryIdError,
)

LOGGER = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get("/match/{substring}")
async def match_files(request):
    substring = request.match_info["substring"]  # e.g., cred def id, issuer DID, tag
    storage_path = request.app["settings"]["storage_path"]
    tails_files = [
        join(storage_path, f)
        for f in os.listdir(storage_path)
        if isfile(join(storage_path, f)) and substring in f
    ]
    return web.json_response(tails_files)


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

    # Check content-type for multipart
    content_type_header = request.headers.get("Content-Type")
    if "multipart" not in content_type_header:
        LOGGER.debug(f"Bad Content-Type header: {content_type_header}")
        raise web.HTTPBadRequest(text="Expected mutlipart content type")

    reader = await request.multipart()

    # Get genesis transactions
    field = await reader.next()
    if field.name != "genesis":
        LOGGER.debug(f"First field is not `genesis`, it's {field.name}")
        raise web.HTTPBadRequest(
            text="First field in multipart request must have name 'genesis'"
        )
    genesis_txn_bytes = await field.read()

    # Lookup revocation registry and get tailsHash
    revocation_reg_id = request.match_info["revocation_reg_id"]
    try:
        revocation_registry_definition = await get_rev_reg_def(
            genesis_txn_bytes, revocation_reg_id, storage_path
        )
    except BadGenesisError:
        LOGGER.debug(f"Received invalid genesis transactions")
        raise web.HTTPBadRequest(text="Genesis transactions are not valid.")
    except BadRevocationRegistryIdError:
        LOGGER.debug(f"Revocation registry id is not valid: {revocation_reg_id}")
        raise web.HTTPBadRequest(
            text=f"Revocation registry ID is not valid: {revocation_reg_id}."
        )

    if not revocation_registry_definition:
        LOGGER.debug(f"Revocation registry not found for id {revocation_reg_id}")
        raise web.HTTPNotFound()

    tails_hash = revocation_registry_definition["value"]["tailsHash"]

    # Get second field
    field = await reader.next()
    if field.name != "tails":
        LOGGER.debug(f"Second field is not `tails`, it's {field.name}")
        raise web.HTTPBadRequest(
            text="Second field in multipart request must have name 'tails'"
        )

    # Process the file in chunks so we don't explode on large files.
    # Construct hash and write file in chunks.
    sha256 = hashlib.sha256()
    try:
        # This should be atomic across networked filesystems:
        # https://linux.die.net/man/3/open
        # http://nfs.sourceforge.net/ (D10)
        # 'x' mode == O_EXCL | O_CREAT
        with NamedTemporaryFile("w+b") as tmp_file:
            while True:
                chunk = await field.read_chunk(CHUNK_SIZE)
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
            with open(
                os.path.join(storage_path, revocation_reg_id), "xb"
            ) as tails_file:
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
