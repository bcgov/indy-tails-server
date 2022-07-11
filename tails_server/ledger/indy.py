import logging
import indy_vdr
from tempfile import NamedTemporaryFile

from tails_server.ledger.base import BaseLedger, BadGenesisError, BadRevocationRegistryIdError

logger = logging.getLogger(__name__)


class IndySdkLedger(BaseLedger):
    """Indy ledger class."""

    BACKEND_NAME = "indy"

    async def get_rev_reg_def(self, genesis_txn_bytes, rev_reg_id, storage_path):
        pool = None
        try:
            # Write the genesis transactions to the file system
            with NamedTemporaryFile("w+b") as tmp_file:
                # Let's test the genesis file before we store it permanently
                tmp_file.write(genesis_txn_bytes)
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
            try:
                req = indy_vdr.ledger.build_get_revoc_reg_def_request(None, rev_reg_id)
            except indy_vdr.error.VdrError as e:
                logger.info(e.code)
                if e.code == indy_vdr.VdrErrorCode.INPUT:
                    raise BadRevocationRegistryIdError()
                else:
                    raise

            resp = await pool.submit_request(req)
        finally:
            if pool:
                pool.close()

        try:
            return resp["data"]
        except KeyError:
            return None
