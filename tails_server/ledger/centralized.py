import logging
from tempfile import NamedTemporaryFile

from aiohttp import ClientSession

from tails_server.ledger.base import BaseLedger

logger = logging.getLogger(__name__)


class CentralizedSdkLedger(BaseLedger):
    """Indy ledger class."""

    BACKEND_NAME = "centralized"

    async def get_rev_reg_def(self, genesis_txn_bytes, rev_reg_id, storage_path):
        # Write the genesis transactions to the file system
        with NamedTemporaryFile("w+b") as tmp_file:
            # Let's test the genesis file before we store it permanently
            tmp_file.write(genesis_txn_bytes)
            tmp_file.seek(0)

        # Get transaction from ledger
        async with ClientSession() as session:
            async with session.get(
                    "http://host.docker.internal:8080" + "/api/revocationDefinition/" + rev_reg_id
            ) as resp:
                if resp.status == 200:
                    resp = await resp.json()
                    return resp
        return None
