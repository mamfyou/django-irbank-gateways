from abc import ABC, abstractmethod


class TransactionHandler(ABC):
    @abstractmethod
    def create_transaction(self, *args):
        pass

    @abstractmethod
    def update_transaction(self, transaction, update_fields: dict):
        pass
