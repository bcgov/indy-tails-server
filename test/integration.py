import argparse
import asyncio
import aiohttp
import base64
import json
import os
from random import randrange

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
    "tag": "cred_def_tag",
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


async def publish_revoc_reg(pool):
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
        REVOC_REG_DEF["tag"],
        ISSUER["cred_def_id"],
        REVOC_REG_DEF["config"],
        ISSUER["tails_writer"],
    )
    req = indy_vdr.ledger.build_revoc_reg_def_request(
        ISSUER["did"], ISSUER["rev_reg_def"]
    )
    return (await pool.submit_request(sign_request(req)))["txn"]["data"]


async def run_tests(genesis_url, tails_server_url):
    rich_traceback_install()
    session = aiohttp.ClientSession()

    log_event("Setting up indy environment...")
    log_event("Downloading genesis transactions...")
    async with session.get(genesis_url) as resp:
        with NamedTemporaryFile("w+b") as tmp_file:
            tmp_file.write(await resp.read())
            tmp_file.seek(0)
            log_event("Connecting to ledger...")
            pool = await connect_to_ledger(tmp_file.name)
    log_event("Creating wallet...")
    await create_issuer_wallet()
    log_event("Publishing schema to ledger...")
    await publish_schema(pool)
    log_event("Publishing credential definition to ledger...")
    await publish_cred_def(pool)
    log_event("Publishing revocation registry to ledger...")
    revo_reg_def = await publish_revoc_reg(pool)
    pool.close()

    await test_happy_path(genesis_url, tails_server_url, revo_reg_def)


async def test_happy_path(genesis_url, tails_server_url, revo_reg_def):
    log_event("Testing happy path...", panel=True)
    session = aiohttp.ClientSession()

    async with session.get(genesis_url) as resp:
        genesis_txn_bytes = await resp.read()

    b64_genesis = base64.b64encode(genesis_txn_bytes)

    import chardet
    with open(revo_reg_def["value"]["tailsLocation"], "rb") as f:
        rprint(chardet.detect(f.read()))
        await asyncio.sleep(90000)

        async with session.put(
            f"{tails_server_url}/{revo_reg_def['id']}",
            headers={"X-Genesis-Transactions": b64_genesis.decode("utf-8")},
        ) as resp:
            rprint(await resp.text())


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
