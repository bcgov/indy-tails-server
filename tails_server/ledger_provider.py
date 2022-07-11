from tails_server.ledger.centralized import CentralizedSdkLedger
from tails_server.ledger.indy import IndySdkLedger
from tails_server.ledger.base import BaseLedger


class BadLedgerError(Exception):
    pass


class LedgerProvider:
    """
    Init a ledger provider class which is able to retrieve the correct ledger class
    according to the specified settings.
    """

    TAILS_SERVER_SUPPORTED_LEDGERS = {
        IndySdkLedger.BACKEND_NAME: IndySdkLedger,
        CentralizedSdkLedger.BACKEND_NAME: CentralizedSdkLedger
    }

    def __init__(self, ledger_type: bytearray):
        """Create a new ledger provider."""
        self.ledger_type = ledger_type.decode()

    def get_ledger(self) -> BaseLedger:
        """Retrieve the correct ledger."""
        if self.ledger_type not in self.TAILS_SERVER_SUPPORTED_LEDGERS:
            raise BadLedgerError()
        return self.TAILS_SERVER_SUPPORTED_LEDGERS[self.ledger_type]()
