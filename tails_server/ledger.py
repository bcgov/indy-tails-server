import logging
import os

import hashlib
from pathlib import Path

from tempfile import NamedTemporaryFile
import base64

from binascii import Error as BinAsciiError
import indy_vdr

logger = logging.getLogger(__name__)


class GenesisDecodeError(Exception):
    pass


class BadGenesisError(Exception):
    pass


async def get_rev_reg_def(b64_genesis, rev_reg_id, storage_path):
    # Decode base into genesis transactions
    try:
        genesis_txn = base64.decodestring(str.encode(b64_genesis))
    except BinAsciiError:
        logger.warn(
            "Could not decode genesis transactions for request with rev_reg_id: "
            + f"{rev_reg_id}"
        )
        raise GenesisDecodeError()

    # We namespace our storage on the digest of the base64 encoded genesis transactions
    sha256 = hashlib.sha256()
    sha256.update(genesis_txn)
    digest = sha256.hexdigest()

    # Write the genesis transactions to the file system
    with NamedTemporaryFile("w+b") as tmp_file:
        # Let's test the genesis file before we store it permanently
        tmp_file.write(genesis_txn)
        tmp_file.seek(0)
        # Try to connect to ledger
        try:
            pool = await indy_vdr.open_pool(transactions_path=tmp_file.name)
        except indy_vdr.error.VdrError as e:
            if e.code == indy_vdr.VdrErrorCode.INPUT:
                raise BadGenesisError()
            else:
                raise

        Path(os.path.join(storage_path, digest)).mkdir(parents=False, exist_ok=True)
        genesis_path = os.path.join(storage_path, digest, "genesis")
        with open(genesis_path, "xb") as genesis_file:
            genesis_file.write(genesis_txn)

    # Connect to ledger
    pool = await indy_vdr.open_pool(transactions_path=genesis_path)

    logger.info(pool)

    logger.info(genesis_txn)
    return False
