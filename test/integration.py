import argparse
import asyncio
import hashlib
import io
import json
import os
from random import randrange
from tempfile import NamedTemporaryFile
from typing import Any

import aiofiles
import aiohttp
import base58
import indy_vdr
import nacl.signing
from anoncreds import CredentialDefinition, RevocationRegistryDefinition, Schema
from indy_vdr.request import Request
from rich import print as rprint
from rich.panel import Panel

ISSUER: dict[str, str] = {
    "seed": "00000000000000000000000000000000",
    "did": "4QxzWk3ajdnEA37NdNU5Kt",
}

SCHEMA: dict[str, str | list[str]] = {
    "name": "DL",
    "version": f"{randrange(10000)}.{randrange(10000)}.{randrange(10000)}",
    "attributes": ["age", "sex", "height", "name"],
}

CRED_DEF: dict[str, str | bool] = {
    "tag": "cred_def_tag",
    "type": "CL",
    "support_revocation": True,
}

REVOC_REG_DEF: dict[str, str | int] = {
    "registry_type": "CL_ACCUM",
    "max_cred_num": 5,
    "issuance_type": "ISSUANCE_ON_DEMAND",
    "tag": "rev_reg_tag",
}


async def create_did(seed: str) -> tuple[str, str]:
    # TODO: remove need for nacl and only use askar
    # Generate an Ed25519 keypair using the same method as Indy SDK
    signing_key = nacl.signing.SigningKey(seed.encode())
    verify_key = signing_key.verify_key
    # Extract the first 16 bytes of the public key
    did_bytes = verify_key.encode()[:16]

    # Convert to base58 to get the DID
    did = base58.b58encode(did_bytes).decode()
    verify_key = base58.b58encode(verify_key.encode()).decode()
    return did, verify_key


def create_schema(
    issuer_did: str, name: str, version: str, attrs: list[str]
) -> tuple[Schema, str]:
    schema_id = f"{issuer_did}:2:{name}:{version}"
    return (
        Schema.create(
            issuer_id=issuer_did, name=name, version=version, attr_names=attrs
        ),
        schema_id,
    )


def log_event(msg: str, panel: bool = False, error: bool = False):
    if not error:
        msg = f"[bright_green]{msg}"
    else:
        msg = f"[bright_red]{msg}"

    if panel:
        msg = Panel(msg)

    rprint(msg)


def sign_request(req: Request, seed: str):
    key = nacl.signing.SigningKey(seed.encode("ascii"))
    signed = key.sign(req.signature_input)
    req.set_signature(signed.signature)
    return req


async def connect_to_ledger(genesis_txn_path: str):
    return await indy_vdr.open_pool(transactions_path=genesis_txn_path)


# Register Issuer DID as Endorser using Steward
async def register_issuer_did(pool: indy_vdr.Pool):

    log_event("Generating and storing Steward DID and verkey...")
    steward_seed = "000000000000000000000000Steward1"

    steward_did, steward_verkey = await create_did(steward_seed)

    log_event(
        f"Generating and storing Issuer DID and verkey {steward_did}:{steward_verkey}..."
    )
    issuer_did, issuer_verkey = await create_did(ISSUER["seed"])

    log_event(f"Registering issuer DID {issuer_did}:{issuer_verkey}...")
    req = indy_vdr.ledger.build_nym_request(
        steward_did, issuer_did, verkey=issuer_verkey, role="ENDORSER"
    )
    await pool.submit_request(sign_request(req, steward_seed))


async def publish_schema(pool: indy_vdr.Pool):
    schema, schema_id = create_schema(
        ISSUER["did"], SCHEMA["name"], SCHEMA["version"], attrs=SCHEMA["attributes"]
    )

    # Add missing fields
    tmp = schema.to_json()
    json1_data: dict[str, Any] = json.loads(tmp)
    json1_data["ver"] = "1.0"
    json1_data["id"] = schema_id

    ISSUER["schema_id"], ISSUER["schema"] = schema_id, json.dumps(json1_data)

    req = indy_vdr.ledger.build_schema_request(ISSUER["did"], ISSUER["schema"])
    resp = await pool.submit_request(sign_request(req, ISSUER["seed"]))
    CRED_DEF["seqNo"] = resp["txnMetadata"]["seqNo"]
    schema_dict = json.loads(ISSUER["schema"])
    schema_dict["seqNo"] = resp["txnMetadata"]["seqNo"]
    ISSUER["schema"] = json.dumps(schema_dict)
    return json.dumps(schema_dict)


def make_cred_def_id() -> str:
    """Derive the ID for a credential definition."""
    return f"{ISSUER['did']}:3:{CRED_DEF['type']}:{CRED_DEF['seqNo']}:{CRED_DEF['tag']}"


async def publish_cred_def(pool: indy_vdr.Pool):

    (cred_def, _, _) = CredentialDefinition.create(
        schema_id=ISSUER["schema_id"],
        schema=ISSUER["schema"],
        issuer_id=ISSUER["did"],
        tag=CRED_DEF["tag"],
        signature_type=CRED_DEF["type"],
        support_revocation=CRED_DEF["support_revocation"],
    )

    # Add missing fields needed by indy_vdr
    cd = cred_def.to_dict()
    cd["ver"] = "1.0"
    cd["id"] = make_cred_def_id()
    cd["schemaId"] = str(CRED_DEF["seqNo"])

    ISSUER["cred_def"] = cd

    req = indy_vdr.ledger.build_cred_def_request(ISSUER["did"], ISSUER["cred_def"])
    json.dumps(await pool.submit_request(sign_request(req, ISSUER["seed"])))


async def publish_revoc_reg(pool: indy_vdr.Pool, tag):
    rev_reg_def, rev_reg_def_private = RevocationRegistryDefinition.create(
        cred_def_id=make_cred_def_id(),
        cred_def=ISSUER["cred_def"],
        issuer_id=ISSUER["did"],
        tag=tag,
        registry_type=REVOC_REG_DEF["registry_type"],
        max_cred_num=REVOC_REG_DEF["max_cred_num"],
    )

    # add missing fields
    json_data = rev_reg_def.to_dict()
    json_data["id"] = f"{ISSUER['did']}:4:{make_cred_def_id()}:CL_ACCUM:{tag}"
    json_data["ver"] = "1.0"
    json_data["schemaId"] = CRED_DEF["seqNo"]
    json_data["value"]["issuanceType"] = REVOC_REG_DEF["issuance_type"]

    rev_reg_def = json_data

    req = indy_vdr.ledger.build_revoc_reg_def_request(ISSUER["did"], rev_reg_def)

    return (await pool.submit_request(sign_request(req, ISSUER["seed"])))["txn"]["data"]


async def run_tests(genesis_url, tails_server_url):
    async with aiohttp.ClientSession() as session:
        log_event("Setting up indy environment...")
        log_event("Downloading genesis transactions...")
        async with session.get(genesis_url) as resp:
            with NamedTemporaryFile("w+b", delete=False) as genesis_file:
                genesis_file.write(await resp.read())
                genesis_file.seek(0)

    log_event("Connecting to ledger...")
    pool = await connect_to_ledger(genesis_file.name)
    log_event("Registering DID to ledger...")
    await register_issuer_did(pool)
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
    await test_put_file_by_hash(tails_server_url)
    await test_put_file_by_hash_x_version_tag(tails_server_url)
    await test_put_file_by_hash_x_file_size(tails_server_url)

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
    async with aiohttp.ClientSession() as session:
        with (
            open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file,
            open(genesis_path, "rb") as genesis_file,
        ):
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
    async with aiohttp.ClientSession() as session:
        with (
            open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file,
            open(genesis_path, "rb") as genesis_file,
        ):
            async with session.put(
                f"{tails_server_url}/bad-id",
                data={"genesis": genesis_file, "tails": tails_file},
            ) as resp:
                assert resp.status == 400
    log_event("Passed")


async def test_upload_already_exist(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing upload already exists...", panel=True)
    async with aiohttp.ClientSession() as session:
        with (
            open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file,
            open(genesis_path, "rb") as genesis_file,
        ):
            # First upload
            async with session.put(
                f"{tails_server_url}/{revo_reg_def['id']}",
                data={"genesis": genesis_file, "tails": tails_file},
            ) as resp:
                assert resp.status == 200
        with (
            open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file,
            open(genesis_path, "rb") as genesis_file,
        ):
            # Second upload
            async with session.put(
                f"{tails_server_url}/{revo_reg_def['id']}",
                data={"genesis": genesis_file, "tails": tails_file},
            ) as resp:
                assert resp.status == 409

    log_event("Passed")


async def test_upload_bad_tails_file(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing bad tails file...", panel=True)
    async with aiohttp.ClientSession() as session:
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

    with (
        open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file,
        open(genesis_path, "rb") as genesis_file,
    ):
        async with session.put(
            f"{tails_server_url}/{revo_reg_def['id']}",
            data={"genesis": genesis_file, "tails": tails_file},
            headers={"Content-Type": "bad"},
        ) as resp:
            assert resp.status == 400

    await session.close()
    log_event("Passed")


async def test_bad_field_order(genesis_path, tails_server_url, revo_reg_def):
    log_event("Testing happy path...", panel=True)
    session = aiohttp.ClientSession()

    with (
        open(revo_reg_def["value"]["tailsLocation"], "rb") as tails_file,
        open(genesis_path, "rb") as genesis_file,
    ):
        async with session.put(
            f"{tails_server_url}/{revo_reg_def['id']}",
            data={"tails": tails_file, "genesis": genesis_file},
        ) as resp:
            assert resp.status == 400
    await session.close()
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
    assert resp1.status == 200, f"resp1.status {resp1.status}"
    assert resp2.status == 409, f"resp2.status {resp2.status}"

    await session.close()
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

    await session.close()
    log_event("Passed")


async def test_put_file_by_hash(tails_server_url):
    file = open("test_tails.bin", "wb+")
    file = io.BytesIO(b"\x00\x02")

    sha256 = hashlib.sha256()
    sha256.update(file.read())
    digest = sha256.digest()
    tails_hash = base58.b58encode(digest).decode("utf-8")

    with aiohttp.MultipartWriter("mixed") as mpwriter:
        file.seek(0)
        mpwriter.append(file.read())
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{tails_server_url}/hash/{tails_hash}",
                data=mpwriter,
            ) as resp:
                assert resp.status == 200
            await session.close()

    file.close()
    os.remove("test_tails.bin")


async def test_put_file_by_hash_x_version_tag(tails_server_url):
    file = open("test_tails_x_version_tag.bin", "wb+")
    file = io.BytesIO(b"\x00\x03")

    sha256 = hashlib.sha256()
    sha256.update(file.read())
    digest = sha256.digest()
    tails_hash = base58.b58encode(digest).decode("utf-8")

    with aiohttp.MultipartWriter("mixed") as mpwriter:
        file.seek(0)
        mpwriter.append(file.read())
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{tails_server_url}/hash/{tails_hash}",
                data=mpwriter,
            ) as resp:
                assert resp.status == 400
                assert await resp.text() == 'Tails file must start with "00 02".'

    file.close()
    os.remove("test_tails_x_version_tag.bin")


async def test_put_file_by_hash_x_file_size(tails_server_url):
    file = open("test_tails_x_file_size.bin", "wb+")
    file = io.BytesIO(b"\x00\x02\x01")

    sha256 = hashlib.sha256()
    sha256.update(file.read())
    digest = sha256.digest()
    tails_hash = base58.b58encode(digest).decode("utf-8")

    with aiohttp.MultipartWriter("mixed") as mpwriter:
        file.seek(0)
        mpwriter.append(file.read())
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{tails_server_url}/hash/{tails_hash}",
                data=mpwriter,
            ) as resp:
                assert resp.status == 400
                assert await resp.text() == "Tails file is not the correct size."

    file.close()
    os.remove("test_tails_x_file_size.bin")


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
