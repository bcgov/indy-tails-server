"""Ledger base class."""

from abc import ABC, abstractmethod, ABCMeta


class BadGenesisError(Exception):
    pass


class BadRevocationRegistryIdError(Exception):
    pass


class BaseLedger(ABC, metaclass=ABCMeta):
    """Base class for ledger."""

    BACKEND_NAME: str = None

    @abstractmethod
    async def get_rev_reg_def(self, genesis_txn_bytes, rev_reg_id, storage_path):
        """Fetch the revocation registry definition from the ledger

        Args:
            genesis_txn_bytes: The genesis transaction file content in byte format
            rev_reg_id: The revocation registry definition ID
            storage_path: The path where to store the genesis file
        """
