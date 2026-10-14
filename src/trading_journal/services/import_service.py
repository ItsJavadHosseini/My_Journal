"""Application service for importing trading history."""

from pathlib import Path
from uuid import UUID

from trading_journal.domain.models import Trade
from trading_journal.imports.base import (
    ImportResult,
    ImportValidationError,
    TradeImporter,
)
from trading_journal.storage.database import Database
from trading_journal.storage.repositories import (
    AccountRepository,
    TradeRepository,
)


class ImportService:
    """Coordinate file parsing and transactional trade-history replacement."""

    def __init__(
        self,
        database: Database,
        importers: tuple[TradeImporter, ...] | None = None,
    ) -> None:
        self.database = database
        self.accounts = AccountRepository(database)
        self.trades = TradeRepository(database)

        if importers is None:
            from trading_journal.imports.csv_importer import CSVTradeImporter
            from trading_journal.imports.excel_importer import ExcelImporter
            from trading_journal.imports.html_importer import HTMLImporter

            importers = (
                CSVTradeImporter(),
                ExcelImporter(),
                HTMLImporter(),
            )

        self.importers = importers
        self._validate_importers()

    def _validate_importers(self) -> None:
        """Reject ambiguous extension ownership."""
        extensions: dict[str, str] = {}

        for importer in self.importers:
            if not isinstance(importer, TradeImporter):
                raise TypeError(
                    "Every importer must implement TradeImporter."
                )

            for extension in importer.supported_extensions:
                normalized = extension.lower()

                if not normalized.startswith("."):
                    raise ValueError(
                        f"Invalid importer extension: {extension!r}"
                    )

                if normalized in extensions:
                    raise ValueError(
                        f"Extension {normalized!r} is registered by both "
                        f"{extensions[normalized]} and "
                        f"{type(importer).__name__}."
                    )

                extensions[normalized] = type(importer).__name__

    def import_file(
        self,
        file_path: str | Path,
        account_id: UUID,
        *,
        allow_empty: bool = False,
    ) -> ImportResult:
        """Parse a supported file and replace the selected account's history."""
        path = Path(file_path).expanduser()

        if not path.exists():
            raise ImportValidationError(f"File not found: {path}")

        if not path.is_file():
            raise ImportValidationError(f"Path is not a file: {path}")

        importer = self._find_importer(path)

        # Parse the entire file before touching existing history.
        result = importer.import_file(path, account_id)

        self.replace_account_trades(
            account_id,
            result,
            allow_empty=allow_empty,
        )

        return result

    def _find_importer(self, path: Path) -> TradeImporter:
        """Choose an importer by file extension."""
        extension = path.suffix.lower()

        for importer in self.importers:
            if importer.supports(path):
                return importer

        supported = sorted(
            {
                extension
                for importer in self.importers
                for extension in importer.supported_extensions
            }
        )

        raise ImportValidationError(
            f"Unsupported file extension {extension!r}. "
            f"Supported extensions: {', '.join(supported)}"
        )

    def replace_account_trades(
        self,
        account_id: UUID,
        result: ImportResult,
        *,
        allow_empty: bool = False,
    ) -> int:
        """Replace one account's trades atomically."""
        if not isinstance(account_id, UUID):
            raise TypeError("account_id must be a UUID.")

        if not isinstance(result, ImportResult):
            raise TypeError("result must be an ImportResult instance.")

        if result.account_id != account_id:
            raise ValueError(
                "The import result belongs to a different account."
            )

        if not result.trades and not allow_empty:
            raise ValueError(
                "The import contains no trades. Existing history was not "
                "changed. Set allow_empty=True only if intentional."
            )

        seen_ids: set[UUID] = set()

        for trade in result.trades:
            if not isinstance(trade, Trade):
                raise TypeError(
                    "Every item in result.trades must be a Trade."
                )

            if trade.account_id != account_id:
                raise ValueError(
                    f"Trade {trade.trade_id} belongs to a different account."
                )

            if trade.trade_id in seen_ids:
                raise ValueError(
                    f"Duplicate trade_id in import: {trade.trade_id}"
                )

            seen_ids.add(trade.trade_id)

        with self.database.transaction() as connection:
            account = self.accounts.get(
                account_id,
                connection=connection,
            )

            if account is None:
                raise LookupError(f"Account not found: {account_id}")

            self.trades.delete_by_account(
                account_id,
                connection=connection,
            )

            self.trades.save_many(
                result.trades,
                connection=connection,
            )

        return len(result.trades)