import argparse
import asyncio
import aiohttp
import base64
import json
import os
import hashlib
import base58
from random import randrange
import aiofiles

from tempfile import NamedTemporaryFile

from rich.traceback import install as rich_traceback_install
from rich import print as rprint
from rich.panel import Panel

import indy
import indy_vdr
import nacl.signing


ISSUER = {
    "seed": "00000000000000000000000000000000",
    "did": "4QxzWk3ajdnEA37NdNU5Kt",
    "wallet_config": json.dumps({"id": "issuer_wallet"}),
    "wallet_credentials": json.dumps({"key": "issuer_wallet_key"}),
}

SCHEMA = {
    "name": "DL",
    "version": f"{randrange(10000)}.{randrange(10000)}.{randrange(10000)}",
    "attributes": '["age", "sex", "height", "name"]',
}

CRED_DEF = {
    "tag": "cred_def_tag",
    "type": "CL",
    "config": json.dumps({"support_revocation": True}),
}

REVOC_REG_DEF = {
    "config": json.dumps({"max_cred_num": 5, "issuance_type": "ISSUANCE_ON_DEMAND"}),
}


def log_event(msg, panel=False, error=False):
    if not error:
        msg = f"[bright_green]{msg}"
    else:
        msg = f"[bright_red]{msg}"

    if panel:
        msg = Panel(msg)

    rprint(msg)


def sign_request(req):
    key = nacl.signing.SigningKey(ISSUER["seed"].encode("ascii"))
    signed = key.sign(req.signature_input)
    req.set_signature(signed.signature)
    return req


async def connect_to_ledger(genesis_txn_path):
    return await indy_vdr.open_pool(transactions_path=genesis_txn_path)


async def create_issuer_wallet():
    await indy.wallet.create_wallet(
        ISSUER["wallet_config"], ISSUER["wallet_credentials"]
    )
    ISSUER["wallet"] = await indy.wallet.open_wallet(
        ISSUER["wallet_config"], ISSUER["wallet_credentials"]
    )


async def publish_schema(pool):
    ISSUER["schema_id"], ISSUER["schema"] = await indy.anoncreds.issuer_create_schema(
        ISSUER["did"], SCHEMA["name"], SCHEMA["version"], SCHEMA["attributes"]
    )
    req = indy_vdr.ledger.build_schema_request(ISSUER["did"], ISSUER["schema"])
    resp = await pool.submit_request(sign_request(req))
    schema_dict = json.loads(ISSUER["schema"])
    schema_dict["seqNo"] = resp["txnMetadata"]["seqNo"]
    ISSUER["schema"] = json.dumps(schema_dict)


async def publish_cred_def(pool):
    (
        ISSUER["cred_def_id"],
        ISSUER["cred_def"],
    ) = await indy.anoncreds.issuer_create_and_store_credential_def(
        ISSUER["wallet"],
        ISSUER["did"],
        ISSUER["schema"],
        CRED_DEF["tag"],
        CRED_DEF["type"],
        CRED_DEF["config"],
    )
    req = indy_vdr.ledger.build_cred_def_request(ISSUER["did"], ISSUER["cred_def"])
    ISSUER["cred_def"] = json.dumps(await pool.submit_request(sign_request(req)))


async def publish_revoc_reg(pool, tag):
    ISSUER["tails_writer_config"] = json.dumps({"base_dir": "tails", "uri_pattern": ""})
    ISSUER["tails_writer"] = await indy.blob_storage.open_writer(
        "default", ISSUER["tails_writer_config"]
    )
    (
        ISSUER["rev_reg_id"],
        ISSUER["rev_reg_def"],
        ISSUER["rev_reg_entry"],
    ) = await indy.anoncreds.issuer_create_and_store_revoc_reg(
        ISSUER["wallet"],
        ISSUER["did"],
        None,
        tag,
        ISSUER["cred_def_id"],
        REVOC_REG_DEF["config"],
        ISSUER["tails_writer"],
    )
    req = indy_vdr.ledger.build_revoc_reg_def_request(
        ISSUER["did"], ISSUER["rev_reg_def"]
    )
    return (await pool.submit_request(sign_request(req)))["txn"]["data"]


async def run_tests(genesis_url, tails_server_url):
    # rich_traceback_install()
    session = aiohttp.ClientSession()

    log_event("Setting up indy environment...")
    log_event("Downloading genesis transactions...")
    async with session.get(genesis_url) as resp:
        with NamedTemporaryFile("w+b", delete=False) as genesis_file:
            genesis_file.write(await resp.read())
            genesis_file.seek(0)

    log_event("Connecting to ledger...")
    pool = await connect_to_ledger(genesis_file.name)
    log_event("Creating wallet...")
    await create_issuer_wallet()
    log_event("Publishing schema to ledger...")
    await publish_schema(pool)
    log_event("Publishing credential definition to ledger...")
    await publish_cred_def(pool)

    log_event("Publishing revocation registry to ledger...")
    revo_reg_def = await publish_revoc_reg(pool, "1")
    pool.close()

    await test_happy_path(genesis_file.name, tails_server_url, revo_reg_def)

    pool = await connect_to_ledger(genesis_file.name)
    log_event("Publishing revocation registry to ledger...")
    revo_reg_def = await publish_revoc_reg(pool, "2")
    pool.close()

    await test_bad_revoc_reg_id_404(genesis_file.name, tails_server_url, revo_reg_def)

    pool = await connect_to_ledger(genesis_file.name)
    log_event("Publishing revocation registry to ledger...")
    revo_reg_def = await publish_revoc_reg(pool, "3")
    pool.close()

    await test_upload_already_exist(genesis_file.name, tails_server_url, revo_reg_def)

    pool = await connect_to_ledger(genesis_file.name)
    log_event("Publishing revocation registry to ledger...")
    revo_reg_def = await publish_revoc_reg(pool, "4")
    pool.close()

    await test_upload_bad_tails_file(genesis_file.name, tails_server_url, revo_reg_def)

    pool = await connect_to_ledger(genesis_file.name)
    log_event("Publishing revocation registry to ledger...")
    revo_reg_def = await publish_revoc_reg(pool, "5")
    pool.close()

    await test_bad_content_type(genesis_file.name, tails_server_url, revo_reg_def)

    pool = await connect_to_ledger(genesis_file.name)
    log_event("Publishing revocation registry to ledger...")
    revo_reg_def = await publish_revoc_reg(pool, "6")
    pool.close()

    await test_bad_field_order(genesis_file.name, tails_server_url, revo_reg_def)

    pool = await connect_to_ledger(genesis_file.name)
    log_event("Publishing revocation registry to ledger...")
    revo_reg_def = await publish_revoc_reg(pool, "7")
    pool.close()

    await test_race_upload(genesis_file.name, tails_server_url, revo_reg_def)

    pool = await connect_to_ledger(genesis_file.name)
    log_event("Publishing revocation registry to ledger...")
    revo_reg_def = await publish_revoc_reg(pool, "8")
    pool.close()

    await test_race_download(genesis_file.name, tails_server_url, revo_reg_def)


async def test_happy_path(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing happy path...", panel=True)
    session = aiohttp.ClientSession()

    with open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file, open(
        genesis_path, "rb"
    ) as genesis_file:
        async with session.put(
            f"{tails_server_url}/{revo_reg_def['id']}",
            data={"genesis": genesis_file, "tails": tails_file},
        ) as resp:
            assert resp.status == 200
    log_event("Passed")

    # Find matching tails file
    async with session.get(
        f"{tails_server_url}/match/{revo_reg_def['credDefId']}"
    ) as resp:
        # Upload is complete so this should succeed
        assert resp.status == 200
        matches = json.loads(await resp.read())
        assert matches


async def test_bad_revoc_reg_id_404(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing bad revocation registry id...", panel=True)
    session = aiohttp.ClientSession()

    with open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file, open(
        genesis_path, "rb"
    ) as genesis_file:
        async with session.put(
            f"{tails_server_url}/bad-id",
            data={"genesis": genesis_file, "tails": tails_file},
        ) as resp:
            assert resp.status == 400

    log_event("Passed")


async def test_upload_already_exist(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing upload already exists...", panel=True)
    session = aiohttp.ClientSession()

    with open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file, open(
        genesis_path, "rb"
    ) as genesis_file:
        # First upload
        async with session.put(
            f"{tails_server_url}/{revo_reg_def['id']}",
            data={"genesis": genesis_file, "tails": tails_file},
        ) as resp:
            assert resp.status == 200

    with open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file, open(
        genesis_path, "rb"
    ) as genesis_file:
        # Second upload
        async with session.put(
            f"{tails_server_url}/{revo_reg_def['id']}",
            data={"genesis": genesis_file, "tails": tails_file},
        ) as resp:
            assert resp.status == 409

    log_event("Passed")


async def test_upload_bad_tails_file(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing bad tails file...", panel=True)
    session = aiohttp.ClientSession()

    with open(genesis_path, "rb") as genesis_file:
        async with session.put(
            f"{tails_server_url}/{revo_reg_def['id']}",
            data={"genesis": genesis_file, "tails": b"bad bytes"},
        ) as resp:
            assert resp.status == 400

    log_event("Passed")


async def test_bad_content_type(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing bad content type...", panel=True)
    session = aiohttp.ClientSession()

    with open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file, open(
        genesis_path, "rb"
    ) as genesis_file:
        async with session.put(
            f"{tails_server_url}/{revo_reg_def['id']}",
            data={"genesis": genesis_file, "tails": tails_file},
            headers={"Content-Type": "bad"},
        ) as resp:
            assert resp.status == 400

    log_event("Passed")


async def test_bad_field_order(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing happy path...", panel=True)
    session = aiohttp.ClientSession()

    with open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file, open(
        genesis_path, "rb"
    ) as genesis_file:
        async with session.put(
            f"{tails_server_url}/{revo_reg_def['id']}",
            data={"tails": tails_file, "genesis": genesis_file},
        ) as resp:
            assert resp.status == 400
    log_event("Passed")


async def test_race_upload(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing upload race condition...", panel=True)
    session = aiohttp.ClientSession()

    async def file_sender(file_name, slow):
        async with aiofiles.open(file_name, "rb") as f:
            chunk = await f.read(64 * 1024)
            while chunk:
                yield chunk
                if slow:
                    await asyncio.sleep(5)
                chunk = await f.read(64 * 1024)

    async def upload(slow):
        # Ensure that the slow upload opens the file on the server first...
        if not slow:
            await asyncio.sleep(50)
        with open(genesis_path, "rb") as genesis_file:
            async with session.put(
                f"{tails_server_url}/{revo_reg_def['id']}",
                data={
                    "genesis": genesis_file,
                    "tails": file_sender(revo_reg_def["value"]["tailsLocation"], slow),
                },
            ) as resp:
                return resp

    # Make sure the second request waits on the file lock
    # and eventually returns 409 when it can read the file
    # since the file already exists
    resp1, resp2 = await asyncio.gather(upload(True), upload(False))
    assert resp1.status == 200
    assert resp2.status == 409

    log_event("Passed")


async def test_race_download(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing download race condition...", panel=True)
    session = aiohttp.ClientSession()

    async def file_sender(file_name):
        async with aiofiles.open(file_name, "rb") as f:
            chunk = await f.read(64 * 1024)
            while chunk:
                yield chunk
                await asyncio.sleep(5)
                chunk = await f.read(64 * 1024)

    async def upload():
        with open(genesis_path, "rb") as genesis_file:
            async with session.put(
                f"{tails_server_url}/{revo_reg_def['id']}",
                data={
                    "genesis": genesis_file,
                    "tails": file_sender(revo_reg_def["value"]["tailsLocation"]),
                },
            ) as resp:
                return resp

    sha256 = hashlib.sha256()

    async def download():
        # Ensure that the slow upload opens the file on the server first...
        await asyncio.sleep(50)
        async with session.get(f"{tails_server_url}/{revo_reg_def['id']}") as resp:
            # Upload is complete so this should succeed
            assert resp.status == 200
            data = await resp.read()
            sha256.update(data)
            b58_digest = base58.b58encode(sha256.digest()).decode("utf-8")
            # Check file integrity
            assert b58_digest == revo_reg_def["value"]["tailsHash"]

    # Make sure the upload succeeds opens the connection first,
    # and the download waits for the upload to complete before streaming
    # response data
    resp1, resp2 = await asyncio.gather(upload(), download())
    assert resp1.status == 200

    log_event("Passed")


PARSER = argparse.ArgumentParser(description="Runs integration tests.")
PARSER.add_argument(
    "--genesis-url",
    type=str,
    required=True,
    dest="genesis_url",
    metavar="<genesis_url>",
    help="Specify the url to the genesis transactions for the ledger.",
)
PARSER.add_argument(
    "--tails-server-url",
    type=str,
    required=True,
    dest="tails_server_url",
    metavar="<tails_server_url>",
    help="Specify the url to the tails server.",
)

if __name__ == "__main__":
    args = PARSER.parse_args()
    genesis_url = args.genesis_url
    tails_server_url = args.tails_server_url
    asyncio.run(run_tests(genesis_url, tails_server_url))
