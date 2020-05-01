import logging
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

    # Get transaction from ledger
    req = indy_vdr.ledger.build_get_revoc_reg_def_request(
        None, rev_reg_id
    )
    resp = await pool.submit_request(req)

    try:
        return resp["data"]
    except KeyError:
        return None
