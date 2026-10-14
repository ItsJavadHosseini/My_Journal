
"""Shared contracts for trade-history importers.

Importers parse external files into domain models.
They do not write to the database or modify existing account history.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from trading_journal.domain.models import Trade


class ImportValidationError(ValueError):
    """Raised when an input file cannot be safely imported."""


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Immutable result of parsing a trade-history file.

    This represents successfully parsed data, not a database transaction.
    Replacing an account's existing history is the responsibility of a
    higher-level service.
    """

    account_id: UUID
    trades: tuple[Trade, ...]
    source_path: str
    source_format: str
    rows_read: int
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, UUID):
            raise TypeError("account_id must be a UUID.")

        if not isinstance(self.trades, tuple):
            raise TypeError("trades must be a tuple.")

        if not all(isinstance(trade, Trade) for trade in self.trades):
            raise TypeError("Every item in trades must be a Trade.")

        if any(
            trade.account_id != self.account_id
            for trade in self.trades
        ):
            raise ValueError(
                "Every imported trade must belong to account_id."
            )

        if not isinstance(self.source_path, str) or not self.source_path:
            raise ValueError("source_path must be a non-empty string.")

        if not isinstance(self.source_format, str) or not self.source_format:
            raise ValueError("source_format must be a non-empty string.")

        if (
            not isinstance(self.rows_read, int)
            or isinstance(self.rows_read, bool)
            or self.rows_read < 0
        ):
            raise ValueError("rows_read must be a non-negative integer.")

        if not isinstance(self.warnings, tuple):
            raise TypeError("warnings must be a tuple.")

    @property
    def trade_count(self) -> int:
        """Number of standardized trades parsed from the file."""
        return len(self.trades)


class TradeImporter(ABC):
    """Abstract contract implemented by each supported file importer."""

    supported_extensions: ClassVar[frozenset[str]] = frozenset()

    @abstractmethod
    def import_file(
        self,
        file_path: str | Path,
        account_id: UUID,
    ) -> ImportResult:
        """Parse a file and return standardized trades.

        Args:
            file_path: Path to the source file.
            account_id: Existing domain account identifier to associate
                with every parsed trade.

        Raises:
            ImportValidationError: If the file or its data is invalid.
        """
        raise NotImplementedError

    def supports(self, file_path: str | Path) -> bool:
        """Return whether the filename has a supported extension."""
        extension = Path(file_path).suffix.lower()
        return extension in self.supported_extensions
