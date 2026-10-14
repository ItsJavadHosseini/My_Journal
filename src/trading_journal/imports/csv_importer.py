
"""CSV importer for standardized trade-history tables."""

import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence
from uuid import UUID

from trading_journal.domain.models import Trade, TradeDirection
from trading_journal.imports.base import (
    ImportResult,
    ImportValidationError,
    TradeImporter,
)


class CSVTradeImporter(TradeImporter):
    """Import a flat trade-history table from a CSV or TSV file.

    Supported input:
    - A flat table with recognized trade-history columns.
    - A sectioned CSV report containing a Positions table.

    This importer does not parse Excel workbooks or merge Orders and Deals.
    """

    supported_extensions = frozenset({".csv", ".tsv"})

    _DELIMITERS = (",", ";", "\t")

    _DATE_FORMATS = (
        "%Y.%m.%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
    )

    _SECTION_NAMES = {
        "positions",
        "orders",
        "deals",
    }

    def import_file(
        self,
        file_path: str | Path,
        account_id: UUID,
    ) -> ImportResult:
        """Read a trade-history table and return standardized trades.

        The caller supplies the account identifier. This method never
        writes to storage and never replaces existing account history.

        Raises:
            ImportValidationError: If the file is unreadable, the required
                columns are absent, or any trade row is invalid.
        """
        if not isinstance(account_id, UUID):
            raise TypeError("account_id must be a UUID.")

        path = Path(file_path).expanduser()

        if not path.exists():
            raise ImportValidationError(
                f"Input file does not exist: {path}"
            )

        if not path.is_file():
            raise ImportValidationError(
                f"Input path is not a file: {path}"
            )

        if not self.supports(path):
            raise ImportValidationError(
                f"Unsupported file extension: {path.suffix!r}. "
                f"Supported extensions: {sorted(self.supported_extensions)}"
            )

        text = self._read_text(path)
        rows = self._read_csv_rows(text)

        if not rows:
            raise ImportValidationError("The input file is empty.")

        header_index, data_start_index = self._find_table(rows)

        headers = [self._clean_cell(value) for value in rows[header_index]]
        columns = self._resolve_columns(headers)

        trades: list[Trade] = []
        rows_read = 0

        for row_index in range(data_start_index, len(rows)):
            row = rows[row_index]

            if self._is_empty_row(row):
                continue

            first_cell = self._normalize_header(
                row[0] if row else ""
            )

            # In a sectioned report, only the Positions table is imported.
            if first_cell in self._SECTION_NAMES:
                break

            # Ignore report footers after the data table.
            if first_cell in {"balance", "equity", "creditfacility"}:
                break

            if not self._looks_like_trade_row(row, columns):
                # Do not silently skip an unexpected non-empty row in
                # the middle of the table.
                raise ImportValidationError(
                    f"Unexpected row structure at CSV line "
                    f"{row_index + 1}."
                )

            rows_read += 1

            try:
                trade = self._parse_trade_row(
                    row=row,
                    columns=columns,
                    account_id=account_id,
                    headers=headers,
                )
            except (ValueError, TypeError, InvalidOperation) as exc:
                raise ImportValidationError(
                    f"Invalid trade data at CSV line "
                    f"{row_index + 1}: {exc}"
                ) from exc

            trades.append(trade)

        if not trades:
            raise ImportValidationError(
                "No trade records were found in the input file."
            )

        return ImportResult(
            account_id=account_id,
            trades=tuple(trades),
            source_path=str(path.resolve()),
            source_format="csv",
            rows_read=rows_read,
        )

    @staticmethod
    def _read_text(path: Path) -> str:
        """Read text with common CSV encodings."""
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ImportValidationError(
                f"Could not read input file: {exc}"
            ) from exc

        if not raw:
            raise ImportValidationError("The input file is empty.")

        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            encodings = ("utf-16",)
        else:
            encodings = ("utf-8-sig", "utf-16", "cp1252")

        for encoding in encodings:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        raise ImportValidationError(
            "Could not decode the input file. "
            "Supported encodings include UTF-8 and UTF-16."
        )

    @classmethod
    def _read_csv_rows(cls, text: str) -> list[list[str]]:
        """Detect the delimiter and read the file into rows."""
        sample = text[:8192]

        try:
            dialect = csv.Sniffer().sniff(
                sample,
                delimiters="".join(cls._DELIMITERS),
            )
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = cls._fallback_delimiter(sample)

        try:
            reader = csv.reader(
                text.splitlines(),
                delimiter=delimiter,
                strict=True,
            )
            return list(reader)
        except csv.Error as exc:
            raise ImportValidationError(
                f"CSV parsing failed: {exc}"
            ) from exc

    @classmethod
    def _fallback_delimiter(cls, sample: str) -> str:
        """Choose a delimiter when automatic detection is inconclusive."""
        lines = [
            line for line in sample.splitlines()
            if line.strip()
        ]

        if not lines:
            raise ImportValidationError("The input file is empty.")

        first_line = lines[0]

        counts = {
            delimiter: first_line.count(delimiter)
            for delimiter in cls._DELIMITERS
        }

        delimiter = max(counts, key=counts.get)

        if counts[delimiter] == 0:
            raise ImportValidationError(
                "Could not detect a CSV delimiter."
            )

        return delimiter

    @classmethod
    def _find_table(
        cls,
        rows: Sequence[Sequence[str]],
    ) -> tuple[int, int]:
        """Find the header and first data row of a trade table."""
        positions_index: int | None = None

        for index, row in enumerate(rows):
            if not row:
                continue

            first_cell = cls._normalize_header(row[0])

            if first_cell == "positions":
                positions_index = index
                break

        if positions_index is not None:
            for index in range(positions_index + 1, len(rows)):
                if cls._is_empty_row(rows[index]):
                    continue

                headers = [
                    cls._clean_cell(value)
                    for value in rows[index]
                ]

                if cls._is_trade_header(headers):
                    return index, index + 1

                # A section title appeared before a valid Positions
                # header; the report cannot be parsed safely.
                if cls._normalize_header(rows[index][0]) in {
                    "orders", "deals"
                }:
                    break

            raise ImportValidationError(
                "A Positions section was found, but its trade-table "
                "header could not be recognized."
            )

        # Alternatively, accept a flat CSV whose first rows contain
        # metadata, provided a recognizable table header is present.
        for index, row in enumerate(rows):
            headers = [
                cls._clean_cell(value)
                for value in row
            ]

            if cls._is_trade_header(headers):
                return index, index + 1

        raise ImportValidationError(
            "Could not find a recognized trade-history header. "
            "Expected columns equivalent to Time, Position, Symbol, "
            "Type, Volume, Price, exit Time, exit Price and Profit."
        )

    @classmethod
    def _is_trade_header(cls, headers: Sequence[str]) -> bool:
        """Check whether a row contains the required trade columns."""
        normalized = [
            cls._normalize_header(header)
            for header in headers
        ]

        required = {
            "position",
            "symbol",
            "type",
            "volume",
            "profit",
        }

        if not required.issubset(set(normalized)):
            return False

        time_count = normalized.count("time")
        price_count = normalized.count("price")

        has_entry_time = (
            time_count >= 1
            or "entrytime" in normalized
            or "opentime" in normalized
        )

        has_exit_time = (
            time_count >= 2
            or "exittime" in normalized
            or "closetime" in normalized
        )

        has_entry_price = (
            price_count >= 1
            or "entryprice" in normalized
            or "openprice" in normalized
        )

        has_exit_price = (
            price_count >= 2
            or "exitprice" in normalized
            or "closeprice" in normalized
        )

        return all(
            (
                has_entry_time,
                has_exit_time,
                has_entry_price,
                has_exit_price,
            )
        )

    @classmethod
    def _resolve_columns(
        cls,
        headers: Sequence[str],
    ) -> dict[str, int]:
        """Map semantic fields to column indices.

        Repeated Time and Price headers are resolved by their occurrence
        order, as in the supplied MetaTrader Positions report.
        """
        normalized = [
            cls._normalize_header(header)
            for header in headers
        ]

        def find(
            aliases: set[str],
            *,
            occurrence: int = 0,
        ) -> int | None:
            matches = [
                index
                for index, name in enumerate(normalized)
                if name in aliases
            ]

            if occurrence < len(matches):
                return matches[occurrence]

            return None

        columns: dict[str, int | None] = {
            "entry_time": find(
                {"entrytime", "opentime", "time"},
                occurrence=0,
            ),
            "position_id": find(
                {"position", "positionid", "ticket"},
            ),
            "symbol": find({"symbol", "instrument"}),
            "direction": find({"type", "direction", "side"}),
            "volume": find({"volume", "lots", "size"}),
            "entry_price": find(
                {"entryprice", "openprice", "price"},
                occurrence=0,
            ),
            "stop_loss": find({"sl", "stoploss"}),
            "take_profit": find({"tp", "takeprofit"}),
            "exit_time": find(
                {"exittime", "closetime"},
            ),
            "exit_price": find(
                {"exitprice", "closeprice"},
            ),
            "commission": find({"commission"}),
            "swap": find({"swap"}),
            "reported_profit": find({"profit", "pnl"}),
        }

        # If entry/exit columns use repeated generic names, fall back
        # to the second occurrence of Time and Price.
        if columns["exit_time"] is None:
            columns["exit_time"] = find({"time"}, occurrence=1)

        if columns["exit_price"] is None:
            columns["exit_price"] = find({"price"}, occurrence=1)

        missing = [
            name
            for name in (
                "entry_time",
                "position_id",
                "symbol",
                "direction",
                "volume",
                "entry_price",
                "exit_time",
                "exit_price",
                "reported_profit",
            )
            if columns[name] is None
        ]

        if missing:
            raise ImportValidationError(
                "Missing required columns: " + ", ".join(missing)
            )

        return {
            name: index
            for name, index in columns.items()
            if index is not None
        }

    @staticmethod
    def _clean_cell(value: str) -> str:
        """Normalize whitespace without changing numeric punctuation."""
        return value.strip().replace("\ufeff", "")

    @staticmethod
    def _normalize_header(value: str) -> str:
        """Normalize header labels for case- and punctuation-insensitive matching."""
        return re.sub(
            r"[^a-z0-9]",
            "",
            value.strip().lower(),
        )

    @classmethod
    def _is_empty_row(cls, row: Sequence[str]) -> bool:
        return not row or all(not value.strip() for value in row)

    @staticmethod
    def _looks_like_trade_row(
        row: Sequence[str],
        columns: dict[str, int],
    ) -> bool:
        """Check that a row has enough cells for all required fields."""
        required_fields = (
            "entry_time",
            "position_id",
            "symbol",
            "direction",
            "volume",
            "entry_price",
            "exit_time",
            "exit_price",
            "reported_profit",
        )

        return all(
            columns[name] < len(row)
            for name in required_fields
        )

    @classmethod
    def _parse_trade_row(
        cls,
        *,
        row: Sequence[str],
        columns: dict[str, int],
        account_id: UUID,
        headers: Sequence[str],
    ) -> Trade:
        """Convert a raw table row into a validated domain Trade."""
        def value(name: str) -> str:
            index = columns.get(name)

            if index is None or index >= len(row):
                return ""

            return cls._clean_cell(row[index])

        position_id = value("position_id")

        if not position_id:
            raise ValueError("Position identifier is empty.")

        symbol = value("symbol")

        direction_text = value("direction").strip().upper()

        try:
            direction = TradeDirection(direction_text)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported trade direction: {direction_text!r}"
            ) from exc

        entry_time = cls._parse_datetime(
            value("entry_time"),
            field_name="entry_time",
        )

        exit_time = cls._parse_datetime(
            value("exit_time"),
            field_name="exit_time",
        )

        entry_price = cls._parse_decimal(
            value("entry_price"),
            field_name="entry_price",
            required=True,
        )

        exit_price = cls._parse_decimal(
            value("exit_price"),
            field_name="exit_price",
            required=True,
        )

        volume = cls._parse_decimal(
            value("volume"),
            field_name="volume",
            required=True,
        )

        stop_loss = cls._parse_decimal(
            value("stop_loss"),
            field_name="stop_loss",
            required=False,
        )

        take_profit = cls._parse_decimal(
            value("take_profit"),
            field_name="take_profit",
            required=False,
        )

        commission = cls._parse_decimal(
            value("commission"),
            field_name="commission",
            required=False,
        )

        swap = cls._parse_decimal(
            value("swap"),
            field_name="swap",
            required=False,
        )

        reported_profit = cls._parse_decimal(
            value("reported_profit"),
            field_name="reported_profit",
            required=True,
        )

        # Preserve source columns by index so duplicate header names
        # do not overwrite one another.
        source_data: dict[str, object] = {}

        occurrence_count: dict[str, int] = {}

        for index, header in enumerate(headers):
            key = header or f"column_{index + 1}"
            occurrence_count[key] = occurrence_count.get(key, 0) + 1

            if occurrence_count[key] > 1:
                key = f"{key}__{occurrence_count[key]}"

            source_data[key] = (
                cls._clean_cell(row[index])
                if index < len(row)
                else ""
            )

        return Trade(
            account_id=account_id,
            position_id=position_id,
            symbol=symbol,
            direction=direction,
            volume=volume,
            entry_time=entry_time,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exit_time=exit_time,
            exit_price=exit_price,
            commission=commission,
            swap=swap,
            reported_profit=reported_profit,
            source_data=source_data,
        )

    @classmethod
    def _parse_datetime(
        cls,
        value: str,
        *,
        field_name: str,
    ) -> datetime:
        """Parse supported trade-history datetime formats."""
        value = value.strip()

        if not value:
            raise ValueError(f"{field_name} is empty.")

        for date_format in cls._DATE_FORMATS:
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported datetime format for {field_name}: "
                f"{value!r}"
            ) from exc

    @staticmethod
    def _parse_decimal(
        value: str,
        *,
        field_name: str,
        required: bool,
    ) -> Decimal | None:
        """Parse a numeric cell while handling common report formatting.

        Examples:
            '4 413.86' -> Decimal('4413.86')
            '- 0.35'   -> Decimal('-0.35')
            '1,234.56' -> Decimal('1234.56')
            '1,25'     -> Decimal('1.25')

        When a value uses a comma without a decimal point, three digits
        after the comma are interpreted as a thousands separator.
        """
        text = value.strip()

        if not text:
            if required:
                raise ValueError(f"{field_name} is empty.")
            return None

        text = (
            text.replace("\u2212", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
        )

        # Reports may separate the sign from the number with whitespace.
        text = re.sub(r"\s+", "", text)

        if "," in text and "." in text:
            # When both separators occur, treat commas as grouping marks.
            text = text.replace(",", "")
        elif "," in text:
            # Heuristic for decimal-comma versus thousands-comma notation.
            if re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+", text):
                text = text.replace(",", "")
            else:
                text = text.replace(",", ".")

        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(
                f"Invalid numeric value for {field_name}: {value!r}"
            ) from exc

        if not number.is_finite():
            raise ValueError(
                f"{field_name} must be a finite number."
            )

        return number
